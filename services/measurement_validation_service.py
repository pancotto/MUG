"""Lightweight measurement-file validation service."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from domain.measurement_validation import (
    STATUS_CORRUPTED,
    STATUS_INVALID,
    STATUS_UNSUPPORTED,
    STATUS_VALID,
    MeasurementValidationResult,
    format_integration_interval,
)


SUPPORTED_SUFFIXES = {".txt", ".xlsx"}
OOXML_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

EMBRASUL_REQUIRED_COLUMNS = {
    "DATA",
    "HORA",
    "Ua",
    "Ub",
    "Uc",
    "Uab",
    "Ubc",
    "Uca",
    "Ia",
    "Ib",
    "Ic",
}


class MeasurementValidationService:
    """Validate parser compatibility without running the full ETL pipeline."""

    def validate(self, file_path: str | Path) -> MeasurementValidationResult:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix not in SUPPORTED_SUFFIXES:
            return MeasurementValidationResult(
                path=path,
                status=STATUS_UNSUPPORTED,
                file_type=suffix[1:].upper() if suffix else "Desconhecido",
                message="Use arquivos .txt ou .xlsx.",
            )

        if not path.exists() or not path.is_file():
            return MeasurementValidationResult(
                path=path,
                status=STATUS_INVALID,
                file_type=suffix[1:].upper(),
                message="O arquivo selecionado não foi encontrado.",
            )

        try:
            if suffix == ".txt":
                return self._validate_txt(path)
            return self._validate_xlsx(path)
        except (BadZipFile, OSError, UnicodeError):
            return MeasurementValidationResult(
                path=path,
                status=STATUS_CORRUPTED,
                file_type=suffix[1:].upper(),
                message="O arquivo selecionado não pôde ser lido.",
            )
        except Exception as exc:
            return MeasurementValidationResult(
                path=path,
                status=STATUS_INVALID,
                file_type=suffix[1:].upper(),
                message=str(exc),
            )

    def _validate_txt(self, path: Path) -> MeasurementValidationResult:
        header_columns: list[str] = []
        manufacturer = ""
        first_values: tuple[bytes, bytes] | None = None
        second_values: tuple[bytes, bytes] | None = None
        last_values: tuple[bytes, bytes] | None = None
        metadata_start: datetime | None = None
        metadata_end: datetime | None = None
        metadata_records: int | None = None
        records = 0
        header_found = False

        for raw_line in path.read_bytes().splitlines():
            line_bytes = raw_line.strip()
            if not line_bytes:
                continue

            if not header_found:
                line = line_bytes.decode("latin1", errors="ignore")
                if (
                    "Primata Tecnologia Eletrônica" in line
                    or "Modelo:P55" in line
                ):
                    manufacturer = "Primata P55"

                metadata_columns = [column.strip() for column in line.split("\t")]
                if len(metadata_columns) >= 2:
                    if metadata_columns[0] == "Início":
                        metadata_start = _parse_excel_serial_datetime(metadata_columns[1])
                    elif metadata_columns[0] == "Fim":
                        metadata_end = _parse_excel_serial_datetime(metadata_columns[1])
                    elif metadata_columns[0] == "N. Registros":
                        metadata_records = _parse_int(metadata_columns[1])

                if line.startswith("Data\tHora"):
                    manufacturer = "Primata P55"
                    header_columns = [column.strip() for column in line.split("\t")]
                    header_found = True
                    continue

                if line.startswith("DATA") and "\tHORA" in line:
                    manufacturer = "Embrasul RE7080"
                    header_columns = [column.strip() for column in line.split("\t")]
                    header_found = True
                    continue

                continue

            values = [value.strip() for value in line_bytes.split(b"\t")]
            if len(values) < 2 or not values[0] or not values[1]:
                continue

            records += 1
            current_values = (values[0], values[1])
            if first_values is None:
                first_values = current_values
            elif second_values is None:
                second_values = current_values
            last_values = current_values

            if (
                metadata_records is not None
                and metadata_start is not None
                and metadata_end is not None
                and second_values is not None
            ):
                break

        if not header_found:
            return MeasurementValidationResult(
                path=path,
                status=STATUS_INVALID,
                file_type="TXT",
                message="Nenhum cabeçalho de medição compatível foi encontrado.",
            )

        compatibility_error = _validate_header_columns(manufacturer, header_columns)
        if compatibility_error:
            return MeasurementValidationResult(
                path=path,
                status=STATUS_INVALID,
                manufacturer=manufacturer or "Não identificado",
                file_type="TXT",
                message=compatibility_error,
            )

        record_count = metadata_records if metadata_records is not None else records
        if record_count <= 0:
            return MeasurementValidationResult(
                path=path,
                status=STATUS_INVALID,
                manufacturer=manufacturer,
                file_type="TXT",
                message="Nenhum registro de medição foi encontrado.",
            )

        return _build_valid_result(
            path=path,
            manufacturer=manufacturer,
            file_type="TXT",
            records=record_count,
            first_datetime=metadata_start or _parse_txt_values_datetime(first_values),
            second_datetime=_parse_txt_values_datetime(second_values),
            last_datetime=metadata_end or _parse_txt_values_datetime(last_values),
        )

    def _validate_xlsx(self, path: Path) -> MeasurementValidationResult:
        with ZipFile(path) as workbook:
            shared_strings = _read_shared_strings(workbook)
            sheet_name = _first_worksheet_name(workbook)
            dimension_last_row = _read_dimension_last_row(workbook, sheet_name)
            header_columns: list[str] = []
            header_found = False
            header_row_index: int | None = None
            metadata_start: datetime | None = None
            metadata_end: datetime | None = None
            metadata_records: int | None = None
            first_values: tuple[object, object] | None = None
            second_values: tuple[object, object] | None = None
            first_datetime: datetime | None = None
            second_datetime: datetime | None = None
            records: int | None = None

            for row_index, row_values in _iter_xlsx_rows(workbook, sheet_name, shared_strings):
                first = _clean_cell(row_values.get("A"))
                second = _clean_cell(row_values.get("B"))

                if first == "Início":
                    metadata_start = _parse_excel_serial_datetime(row_values.get("B"))
                elif first == "Fim":
                    metadata_end = _parse_excel_serial_datetime(row_values.get("B"))
                elif first == "N. Registros":
                    metadata_records = _parse_int(row_values.get("B"))

                if not header_found:
                    if first == "Data" and second.startswith("Hora"):
                        header_columns = [
                            _clean_cell(row_values.get(_column_name(index)))
                            for index in range(1, 256)
                            if _clean_cell(row_values.get(_column_name(index)))
                        ]
                        header_found = True
                        header_row_index = row_index
                    continue

                if not first or not second:
                    continue

                current_values = (row_values.get("A"), row_values.get("B"))
                if first_values is None:
                    first_values = current_values
                    first_datetime = _parse_values_datetime(first_values)
                    continue
                if second_values is None:
                    second_values = current_values
                    second_datetime = _parse_values_datetime(second_values)

                if (
                    header_found
                    and metadata_records is not None
                    and first_datetime is not None
                    and second_datetime is not None
                    and metadata_start is not None
                    and metadata_end is not None
                ):
                    break

            if not header_found:
                return MeasurementValidationResult(
                    path=path,
                    status=STATUS_INVALID,
                    manufacturer="Primata P55",
                    file_type="XLSX",
                    message="Nenhum cabeçalho Primata compatível foi encontrado.",
                )

            compatibility_error = _validate_header_columns("Primata P55", header_columns)
            if compatibility_error:
                return MeasurementValidationResult(
                    path=path,
                    status=STATUS_INVALID,
                    manufacturer="Primata P55",
                    file_type="XLSX",
                    message=compatibility_error,
                )

            records = metadata_records
            if records is None and dimension_last_row is not None and header_row_index is not None:
                records = max(dimension_last_row - header_row_index, 0)

            if not records or records <= 0:
                return MeasurementValidationResult(
                    path=path,
                    status=STATUS_INVALID,
                    manufacturer="Primata P55",
                    file_type="XLSX",
                    message="Nenhum registro de medição foi encontrado.",
                )

            return _build_valid_result(
                path=path,
                manufacturer="Primata P55",
                file_type="XLSX",
                records=records,
                first_datetime=metadata_start or first_datetime,
                second_datetime=second_datetime,
                last_datetime=metadata_end,
            )


def _validate_header_columns(manufacturer: str, columns: list[str]) -> str:
    if manufacturer == "Embrasul RE7080":
        available = set(columns)
        missing = sorted(EMBRASUL_REQUIRED_COLUMNS - available)
        if missing:
            return "Colunas obrigatórias da Embrasul ausentes: " + ", ".join(missing)
        return ""

    if "Data" not in columns or not any(column.startswith("Hora") for column in columns):
        return "Colunas obrigatórias do Primata ausentes: Data, Hora"

    return ""


def _build_valid_result(
    *,
    path: Path,
    manufacturer: str,
    file_type: str,
    records: int,
    first_datetime: datetime | None,
    second_datetime: datetime | None,
    last_datetime: datetime | None,
) -> MeasurementValidationResult:
    integration_seconds = None
    if first_datetime is not None and second_datetime is not None:
        delta = abs((second_datetime - first_datetime).total_seconds())
        if delta > 0:
            integration_seconds = int(round(delta))

    return MeasurementValidationResult(
        path=path,
        status=STATUS_VALID,
        manufacturer=manufacturer,
        file_type=file_type,
        period=_format_period(first_datetime, last_datetime),
        integration_interval=format_integration_interval(integration_seconds),
        records=records,
        message="Medição carregada com sucesso.",
    )


def _format_period(start: datetime | None, end: datetime | None) -> str:
    if start is None:
        return "Não disponível"

    start_text = start.strftime("%d/%m/%Y %H:%M:%S")
    if end is None or end == start:
        return start_text
    return f"{start_text} - {end.strftime('%d/%m/%Y %H:%M:%S')}"


def _clean_cell(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _decode_field(value: bytes) -> str:
    return value.decode("latin1", errors="ignore").strip()


def _parse_txt_values_datetime(values: tuple[bytes, bytes] | None) -> datetime | None:
    if values is None:
        return None
    return _parse_datetime(_decode_field(values[0]), _decode_field(values[1]))


def _parse_values_datetime(values: tuple[object, object] | None) -> datetime | None:
    if values is None:
        return None
    return _parse_datetime(values[0], values[1])


def _parse_excel_serial_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    if isinstance(value, date):
        return datetime.combine(value, time.min)

    raw_value = value
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        if not text:
            return None
        parsed = _parse_text_datetime(text)
        if parsed is not None:
            return parsed
        try:
            raw_value = float(text)
        except ValueError:
            return None

    if isinstance(raw_value, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=float(raw_value))).replace(
            microsecond=0
        )

    return None


def _parse_int(value) -> int | None:
    if isinstance(value, int):
        return value
    text = _clean_cell(value).replace(".", "").replace(",", "")
    if not text.isdigit():
        return None
    return int(text)


def _parse_text_datetime(text: str) -> datetime | None:
    parsed_date = _parse_date_text(text)
    if parsed_date is None:
        return None

    parsed_time = _parse_time_text(text)
    if parsed_time is None:
        parsed_time = time.min

    return datetime.combine(parsed_date, parsed_time)


def _parse_date_text(text: str) -> date | None:
    clean = text.strip().replace("T", " ")
    date_token = clean.split(" ", 1)[0]

    if "/" in date_token:
        parts = date_token.split("/")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            return None
        day = int(parts[0])
        month = int(parts[1])
        year = int(parts[2])
        if year < 100:
            year += 2000 if year < 70 else 1900
        try:
            return date(year, month, day)
        except ValueError:
            return None

    if "-" in date_token:
        parts = date_token.split("-")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            return None
        try:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return None

    return None


def _parse_time_text(text: str) -> time | None:
    token = ""
    for candidate in text.strip().replace("T", " ").split():
        if ":" in candidate:
            token = candidate
            break

    if not token and ":" in text:
        token = text.strip()

    if not token:
        return None

    parts = token.split(":")
    if len(parts) < 2:
        return None

    second_text = parts[2] if len(parts) > 2 else "0"
    second_text = second_text.split(".", 1)[0]
    if not (parts[0].isdigit() and parts[1].isdigit() and second_text.isdigit()):
        return None

    hour = int(parts[0])
    minute = int(parts[1])
    second = int(second_text)

    try:
        return time(hour, minute, second)
    except ValueError:
        return None


def _read_shared_strings(workbook: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []

    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall(f"{OOXML_MAIN_NS}si"):
        text = "".join(node.text or "" for node in item.iter(f"{OOXML_MAIN_NS}t"))
        values.append(text)
    return values


def _first_worksheet_name(workbook: ZipFile) -> str:
    names = workbook.namelist()
    if "xl/worksheets/sheet1.xml" in names:
        return "xl/worksheets/sheet1.xml"

    for name in names:
        if name.startswith("xl/worksheets/") and name.endswith(".xml"):
            return name

    raise ValueError("Nenhuma planilha foi encontrada no arquivo XLSX.")


def _read_dimension_last_row(workbook: ZipFile, sheet_name: str) -> int | None:
    with workbook.open(sheet_name) as handle:
        head = handle.read(4096).decode("utf-8", errors="ignore")

    marker = 'dimension ref="'
    start = head.find(marker)
    if start < 0:
        return None
    start += len(marker)
    end = head.find('"', start)
    if end < 0:
        return None
    last_reference = head[start:end].split(":")[-1]
    digits = "".join(char for char in last_reference if char.isdigit())
    return int(digits) if digits else None


def _iter_xlsx_rows(workbook: ZipFile, sheet_name: str, shared_strings: list[str]):
    with workbook.open(sheet_name) as handle:
        for event, element in ET.iterparse(handle, events=("end",)):
            if element.tag != f"{OOXML_MAIN_NS}row":
                continue

            row_index = int(element.attrib.get("r", "0") or 0)
            row_values: dict[str, object] = {}
            for cell in element.findall(f"{OOXML_MAIN_NS}c"):
                cell_ref = cell.attrib.get("r", "")
                column = _column_letters(cell_ref)
                if not column:
                    continue
                row_values[column] = _xlsx_cell_value(cell, shared_strings)

            yield row_index, row_values
            element.clear()


def _xlsx_cell_value(cell, shared_strings: list[str]):
    cell_type = cell.attrib.get("t")
    value_node = cell.find(f"{OOXML_MAIN_NS}v")

    if cell_type == "inlineStr":
        inline = cell.find(f"{OOXML_MAIN_NS}is")
        if inline is None:
            return ""
        return "".join(node.text or "" for node in inline.iter(f"{OOXML_MAIN_NS}t"))

    raw_value = value_node.text if value_node is not None else ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)]
        except (ValueError, IndexError):
            return ""

    if raw_value == "":
        return ""

    try:
        numeric = float(raw_value)
    except ValueError:
        return raw_value

    if numeric.is_integer():
        return int(numeric)
    return numeric


def _column_letters(cell_ref: str) -> str:
    letters = []
    for char in cell_ref or "":
        if not char.isalpha():
            break
        letters.append(char.upper())
    return "".join(letters)


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _parse_datetime(date_value, time_value) -> datetime | None:
    parsed_date = _parse_date(date_value)
    parsed_time = _parse_time(time_value)

    if isinstance(date_value, datetime) and parsed_time is None:
        return date_value

    if parsed_date is None or parsed_time is None:
        return None

    return datetime.combine(parsed_date, parsed_time)


def _parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and float(value) > 1:
        return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()

    text = _clean_cell(value)
    if not text:
        return None

    return _parse_date_text(text)


def _parse_time(value) -> time | None:
    if isinstance(value, datetime):
        return value.time().replace(microsecond=0)
    if isinstance(value, time):
        return value.replace(microsecond=0)
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds()) % (24 * 60 * 60)
        return _time_from_seconds(total_seconds)
    if isinstance(value, (int, float)) and 0 <= float(value) < 1:
        return _time_from_seconds(int(round(float(value) * 24 * 60 * 60)))

    text = _clean_cell(value).replace(",", ".")
    if not text:
        return None

    return _parse_time_text(text)


def _time_from_seconds(total_seconds: int) -> time:
    total_seconds %= 24 * 60 * 60
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return time(hours, minutes, seconds)
