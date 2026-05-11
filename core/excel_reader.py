from pathlib import Path
from datetime import time
import math

import pandas as pd

from core.models import InputData, ProcessedData
from core.profiling import profile_block, log_profile_event


PRIMATA_HEADER_FIRST_COLUMN = "Data"
PRIMATA_HEADER_SECOND_COLUMN = "Hora "


def process_input_data(input_data: InputData) -> ProcessedData:
    """
    Processa o arquivo informado pelo usuário.

    Aceita:
    - .xlsx exportado pelo Primata P55;
    - .txt exportado pelo Primata P55 convertido/salvo pelo Excel;
    - .txt exportado pelo Embrasul RE7080.

    Internamente, todos são convertidos para o mesmo padrão de DataFrame
    utilizado pela aplicação.
    """
    file_path = Path(input_data.excel_path)
    suffix = file_path.suffix.lower()

    with profile_block("ETL total", file=file_path.name, suffix=suffix):
        if suffix == ".xlsx":
            with profile_block("ETL read Primata XLSX", file=file_path.name):
                dataframe = read_primata_excel(file_path)
            source_type = "primata_xlsx"

        elif suffix == ".txt":
            with profile_block("ETL detect TXT type", file=file_path.name):
                txt_type = detect_txt_type(file_path)

            if txt_type == "primata":
                with profile_block("ETL read Primata TXT", file=file_path.name):
                    dataframe = read_primata_txt(file_path)
            elif txt_type == "embrasul":
                with profile_block("ETL read Embrasul TXT", file=file_path.name):
                    dataframe = read_embrasul_txt_as_primata_dataframe(file_path)
            else:
                raise ValueError("Não foi possível identificar se o arquivo TXT é Primata ou Embrasul.")
            source_type = txt_type

        else:
            raise ValueError("Formato de arquivo não suportado. Utilize .xlsx ou .txt.")

        log_profile_event(
            "ETL raw dataframe",
            source=source_type,
            rows=len(dataframe),
            columns=len(dataframe.columns),
        )

        with profile_block("ETL prepare common dataframe", source=source_type):
            dataframe = prepare_common_dataframe(dataframe)

        with profile_block("ETL infer metadata", rows=len(dataframe), columns=len(dataframe.columns)):
            integration_time = infer_integration_time(dataframe)
            tension = infer_nominal_tension(dataframe)

        equipment_type = input_data.equipment_type
        equipment_reference = input_data.equipment_reference
        equipment_value = float(input_data.equipment_value)

        if equipment_type == "DISJUNTOR":
            # Potência aparente equivalente em kVA para manter compatibilidade
            # com gráficos que usam referência de potência nominal.
            nominal_power_kva = (float(tension) * equipment_value * math.sqrt(3)) / 1000
        else:
            nominal_power_kva = equipment_value

        log_profile_event(
            "ETL processed dataframe",
            rows=len(dataframe),
            columns=len(dataframe.columns),
            integration_time=integration_time,
            tension=tension,
        )

        return ProcessedData(
            company=input_data.company,
            city=input_data.city,
            trafo=nominal_power_kva,
            local=input_data.local,
            revision=input_data.revision,
            excel_path=file_path,
            dataframe=dataframe,
            integration_time=integration_time,
            tension=tension,
            equipment_type=equipment_type,
            equipment_reference=equipment_reference,
            equipment_value=equipment_value,
        )


def read_primata_excel(file_path: Path) -> pd.DataFrame:
    """
    Lê a planilha exportada pelo Primata P55.

    Versão otimizada:
    - lê o Excel apenas uma vez;
    - localiza a linha de cabeçalho;
    - reaproveita o DataFrame bruto;
    - preserva compatibilidade com as colunas esperadas: 'Data' e 'Hora '.
    """
    raw = pd.read_excel(
        file_path,
        sheet_name=0,
        header=None,
        engine="openpyxl",
    )

    header_row = None

    for idx in range(len(raw)):
        first = str(raw.iloc[idx, 0]).strip()
        second = str(raw.iloc[idx, 1]).strip()

        if first == "Data" and second.startswith("Hora"):
            header_row = idx
            break

    if header_row is None:
        raise ValueError("Não foi possível localizar o cabeçalho da planilha Primata.")

    columns = raw.iloc[header_row].tolist()

    dataframe = raw.iloc[header_row + 1:].copy()
    dataframe.columns = columns

    dataframe = dataframe.dropna(how="all")

    dataframe = dataframe.loc[
        :,
        ~pd.Series(dataframe.columns)
        .astype(str)
        .str.contains("^Unnamed", regex=True)
        .values
    ]

    dataframe = normalize_primata_columns(dataframe)

    return dataframe


def detect_txt_type(file_path: Path) -> str:
    """
    Detecta se o arquivo TXT é Primata ou Embrasul.
    """
    with open(file_path, "r", encoding="latin1") as file:
        content = file.read(20000)

    if "Primata Tecnologia Eletrônica" in content or "Modelo:P55" in content:
        return "primata"

    if "DATA" in content and "HORA" in content and "Ua" in content:
        return "embrasul"

    if "Data\tHora" in content and "Tensão A" in content:
        return "primata"

    return "unknown"


def find_primata_txt_header_line(file_path: Path) -> int:
    """
    Localiza a linha do cabeçalho no TXT do Primata.
    """
    with open(file_path, "r", encoding="latin1") as file:
        for index, line in enumerate(file):
            clean_line = line.strip()

            if clean_line.startswith("Data\tHora"):
                return index

    raise ValueError("Não foi possível localizar o cabeçalho Data/Hora no TXT do Primata.")


def read_primata_txt(file_path: Path) -> pd.DataFrame:
    """
    Lê o TXT do Primata salvo como texto delimitado por tabulação.
    O arquivo já vem no mesmo padrão de colunas do XLSX.
    """
    header_line_index = find_primata_txt_header_line(file_path)

    dataframe = pd.read_csv(
        file_path,
        sep="\t",
        header=header_line_index,
        encoding="latin1",
        dtype=str,
        engine="python",
    )

    dataframe = dataframe.dropna(axis=1, how="all")
    dataframe = dataframe.dropna(how="all")

    dataframe = normalize_primata_columns(dataframe)

    if "Data" not in dataframe.columns or "Hora " not in dataframe.columns:
        raise ValueError("O TXT do Primata precisa conter as colunas 'Data' e 'Hora '.")

    return dataframe


def normalize_primata_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza nomes de colunas do Primata preservando compatibilidade
    com o restante da aplicação.
    """
    renamed_columns = {}

    for col in dataframe.columns:
        clean_col = str(col).strip()

        if clean_col == "Data":
            renamed_columns[col] = "Data"
        elif clean_col.startswith("Hora"):
            renamed_columns[col] = "Hora "
        else:
            renamed_columns[col] = clean_col

    return dataframe.rename(columns=renamed_columns)


def read_embrasul_txt_as_primata_dataframe(file_path: Path) -> pd.DataFrame:
    """
    Lê o TXT exportado pelo Embrasul RE7080 e converte para o padrão interno
    equivalente à planilha do Primata.
    """
    header_line_index = find_embrasul_header_line(file_path)

    raw = pd.read_csv(
        file_path,
        sep="\t",
        header=header_line_index,
        encoding="latin1",
        dtype=str,
        engine="python",
    )

    raw = raw.dropna(axis=1, how="all")
    raw.columns = [str(col).strip() for col in raw.columns]
    raw = raw.dropna(how="all")

    required_columns = ["DATA", "HORA", "Ua", "Ub", "Uc", "Uab", "Ubc", "Uca", "Ia", "Ib", "Ic"]

    missing = [col for col in required_columns if col not in raw.columns]
    if missing:
        raise ValueError(
            "O arquivo TXT da Embrasul não possui as colunas obrigatórias: "
            + ", ".join(missing)
        )

    df = pd.DataFrame()

    df["Data"] = parse_embrasul_date(raw["DATA"])
    df["Hora "] = parse_embrasul_time(raw["HORA"])

    df["Tensão A (médio)(V)"] = to_number(raw.get("Ua"))
    df["Tensão B (médio)(V)"] = to_number(raw.get("Ub"))
    df["Tensão C (médio)(V)"] = to_number(raw.get("Uc"))

    df["Corrente A (médio)(A)"] = to_number(raw.get("Ia"))
    df["Corrente B (médio)(A)"] = to_number(raw.get("Ib"))
    df["Corrente C (médio)(A)"] = to_number(raw.get("Ic"))

    df["FP A (médio)(%)"] = to_number(raw.get("FPa")).abs() * 100
    df["FP B (médio)(%)"] = to_number(raw.get("FPb")).abs() * 100
    df["FP C (médio)(%)"] = to_number(raw.get("FPc")).abs() * 100
    df["FP Trifásico (médio)(%)"] = to_number(raw.get("FP3f")).abs() * 100

    pa = to_number(raw.get("Pa"))
    pb = to_number(raw.get("Pb"))
    pc = to_number(raw.get("Pc"))
    p3f = to_number(raw.get("P3f"))

    df["Pot Ativa Cons. A Cons. (médio)(kW)"] = positive_kw(pa)
    df["Pot Ativa Inj. A Forn. (médio)(kW)"] = negative_kw(pa)
    df["Pot Ativa Cons. B Cons. (médio)(kW)"] = positive_kw(pb)
    df["Pot Ativa Inj. B Forn. (médio)(kW)"] = negative_kw(pb)
    df["Pot Ativa Cons. C Cons. (médio)(kW)"] = positive_kw(pc)
    df["Pot Ativa Inj. C Forn. (médio)(kW)"] = negative_kw(pc)

    df["Pot Ativa Cons. Trifásica Cons. (médio)(kW)"] = positive_kw(p3f)
    df["Pot Ativa Inj. Trifásica Forn. (médio)(kW)"] = negative_kw(p3f)

    df["Energia A Cons. (médio)((Kwh))"] = 0
    df["Energia A Forn. (médio)((Kwh))"] = 0
    df["Energia B Cons. (médio)((Kwh))"] = 0
    df["Energia B Forn. (médio)((Kwh))"] = 0
    df["Energia C Cons. (médio)((Kwh))"] = 0
    df["Energia C Forn. (médio)((Kwh))"] = 0
    df["Energia TRI Cons. (médio)((Kwh))"] = 0
    df["Energia TRI Forn. (médio)((Kwh))"] = 0

    qa = to_number(raw.get("Qa"))
    qb = to_number(raw.get("Qb"))
    qc = to_number(raw.get("Qc"))
    q3f = to_number(raw.get("Q3f"))

    df["Pot Reativa Ind. A (médio)(kVAr)"] = positive_kw(qa)
    df["Pot Reativa Cap. A (médio)(kVAr)"] = negative_kw(qa)
    df["Pot Reativa Ind. B (médio)(kVAr)"] = positive_kw(qb)
    df["Pot Reativa Cap. B (médio)(kVAr)"] = negative_kw(qb)
    df["Pot Reativa Ind. C (médio)(kVAr)"] = positive_kw(qc)
    df["Pot Reativa Cap. C (médio)(kVAr)"] = negative_kw(qc)

    df["Pot Reativa Ind. Trifásica (médio)(kVAr)"] = positive_kw(q3f)
    df["Pot Reativa Cap. Trifásica (médio)(kVAr)"] = negative_kw(q3f)

    df["Pot Aparente A (médio)(kVA)"] = to_number(raw.get("Sa")) / 1000
    df["Pot Aparente B (médio)(kVA)"] = to_number(raw.get("Sb")) / 1000
    df["Pot Aparente C (médio)(kVA)"] = to_number(raw.get("Sc")) / 1000
    df["Pot Aparente Trifásica (médio)(kVA)"] = to_number(raw.get("S3f")) / 1000

    df["Frequência (médio)(Hz)"] = to_number(raw.get("Freq"))

    df["DHT VA (médio)(%)"] = to_number(raw.get("DHTua"))
    df["DHT VB (médio)(%)"] = to_number(raw.get("DHTub"))
    df["DHT VC (médio)(%)"] = to_number(raw.get("DHTuc"))

    df["Tensão A (fundamental) (médio)(V)"] = df["Tensão A (médio)(V)"]
    df["Tensão B (fundamental) (médio)(V)"] = df["Tensão B (médio)(V)"]
    df["Tensão C (fundamental) (médio)(V)"] = df["Tensão C (médio)(V)"]

    df["DHT IA (médio)(%)"] = to_number(raw.get("DHTia"))
    df["DHT IB (médio)(%)"] = to_number(raw.get("DHTib"))
    df["DHT IC (médio)(%)"] = to_number(raw.get("DHTic"))

    df["Corrente A (fundamental) (médio)(A)"] = df["Corrente A (médio)(A)"]
    df["Corrente B (fundamental) (médio)(A)"] = df["Corrente B (médio)(A)"]
    df["Corrente C (fundamental) (médio)(A)"] = df["Corrente C (médio)(A)"]

    df["Deseq. Tensão (médio)(%)"] = calculate_voltage_imbalance(
        df["Tensão A (médio)(V)"],
        df["Tensão B (médio)(V)"],
        df["Tensão C (médio)(V)"],
    )

    df["Deseq. Corrente (médio)(%)"] = calculate_current_imbalance(
        df["Corrente A (médio)(A)"],
        df["Corrente B (médio)(A)"],
        df["Corrente C (médio)(A)"],
    )

    df["Tensão Neutro (médio)(V)"] = to_number(raw.get("Un"))
    df["Corr. N. Medida (médio)(A)"] = to_number(raw.get("In"))

    df["Pst A (médio)(pu)"] = 0
    df["Plt A (médio)(pu)"] = 0
    df["Pst B (médio)(pu)"] = 0
    df["Plt B (médio)(pu)"] = 0
    df["Pst C (médio)(pu)"] = 0
    df["Plt C (médio)(pu)"] = 0

    df["Demanda A Cons. (médio)(kW)"] = df["Pot Ativa Cons. A Cons. (médio)(kW)"]
    df["Demanda B Cons. (médio)(kW)"] = df["Pot Ativa Cons. B Cons. (médio)(kW)"]
    df["Demanda C Cons. (médio)(kW)"] = df["Pot Ativa Cons. C Cons. (médio)(kW)"]
    df["Demanda Trifásico Cons. (médio)(kW)"] = df["Pot Ativa Cons. Trifásica Cons. (médio)(kW)"]

    df["Tensao AB (médio)(V)"] = to_number(raw.get("Uab"))
    df["Tensao BC (médio)(V)"] = to_number(raw.get("Ubc"))
    df["Tensao CA (médio)(V)"] = to_number(raw.get("Uca"))

    return df


def find_embrasul_header_line(file_path: Path) -> int:
    with open(file_path, "r", encoding="latin1") as file:
        for index, line in enumerate(file):
            clean_line = line.strip()
            if clean_line.startswith("DATA") and "\tHORA" in clean_line:
                return index

    raise ValueError("Não foi possível localizar o cabeçalho DATA/HORA no TXT da Embrasul.")


def parse_numeric_series(series) -> pd.Series:
    """
    Converte séries numéricas vindas de:
    - Excel: 216.82
    - TXT BR: 216,82
    - TXT com milhar: 1.234,56

    Regra:
    - Se tiver vírgula, trata vírgula como decimal e ponto como milhar.
    - Se não tiver vírgula, preserva ponto como decimal.
    """
    if series is None:
        return pd.Series(dtype=float)

    values = pd.Series(series).astype(str).str.strip()

    has_comma = values.str.contains(",", regex=False)

    converted = values.copy()

    converted.loc[has_comma] = (
        converted.loc[has_comma]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    converted = converted.replace(
        {
            "": None,
            "nan": None,
            "None": None,
            "NaN": None,
            "NaT": None,
        }
    )

    return pd.to_numeric(converted, errors="coerce").fillna(0)


def to_number(series) -> pd.Series:
    return parse_numeric_series(series)


def parse_embrasul_date(series) -> pd.Series:
    return pd.to_datetime(series, format="%d/%m/%Y", errors="coerce")


def parse_embrasul_time(series) -> pd.Series:
    clean = (
        pd.Series(series)
        .astype(str)
        .str.strip()
        .str.replace(",", ".", regex=False)
    )

    parsed = pd.to_datetime(clean, format="%H:%M:%S.%f", errors="coerce")

    fallback = pd.to_datetime(clean, format="%H:%M:%S", errors="coerce")
    parsed = parsed.fillna(fallback)

    return parsed.dt.time


def positive_kw(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0)
    return values.clip(lower=0) / 1000


def negative_kw(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").fillna(0)
    return values.clip(upper=0).abs() / 1000


def calculate_voltage_imbalance(va: pd.Series, vb: pd.Series, vc: pd.Series) -> pd.Series:
    values = pd.concat([va, vb, vc], axis=1)
    avg = values.mean(axis=1)
    max_deviation = values.sub(avg, axis=0).abs().max(axis=1)

    result = (max_deviation / avg.replace(0, pd.NA)) * 100
    return result.fillna(0)


def calculate_current_imbalance(ia: pd.Series, ib: pd.Series, ic: pd.Series) -> pd.Series:
    values = pd.concat([ia, ib, ic], axis=1)
    avg = values.mean(axis=1)
    max_deviation = values.sub(avg, axis=0).abs().max(axis=1)

    result = (max_deviation / avg.replace(0, pd.NA)) * 100
    return result.fillna(0)


def parse_datetime_columns(df: pd.DataFrame) -> pd.Series:
    """
    Monta a coluna Datetime de forma compatível com:
    - Primata TXT: Data = dd/mm/aa e Hora = HH:MM:SS;
    - Primata XLSX: Data pode vir como datetime/Timestamp e Hora como time/string;
    - Embrasul TXT: Data já pode vir parseada e Hora pode vir como time.
    """
    date_raw = df["Data"]
    time_raw = df["Hora "]

    if pd.api.types.is_datetime64_any_dtype(date_raw):
        date_parsed = pd.to_datetime(date_raw, errors="coerce")
    else:
        date_as_text = pd.Series(date_raw, index=df.index).astype(str).str.strip()

        # Primata TXT normalmente usa dd/mm/aa.
        date_parsed = pd.to_datetime(date_as_text, format="%d/%m/%y", errors="coerce")

        # Embrasul e algumas exportações podem usar dd/mm/aaaa.
        if date_parsed.notna().sum() == 0:
            date_parsed = pd.to_datetime(date_as_text, format="%d/%m/%Y", errors="coerce")

        # Primata XLSX convertido para texto pode aparecer como yyyy-mm-dd HH:MM:SS.
        if date_parsed.notna().sum() == 0:
            date_parsed = pd.to_datetime(date_as_text, format="%Y-%m-%d %H:%M:%S", errors="coerce")

        # Fallback amplo, usado apenas se os padrões conhecidos falharem.
        if date_parsed.notna().sum() == 0:
            date_parsed = pd.to_datetime(date_as_text, dayfirst=True, errors="coerce")

    time_series = pd.Series(time_raw, index=df.index)

    def _time_to_text(value):
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")

        if pd.isna(value):
            return None

        if isinstance(value, pd.Timestamp):
            return value.strftime("%H:%M:%S")

        text = str(value).strip().replace(",", ".")

        if not text or text.lower() in {"nan", "nat", "none"}:
            return None

        parsed = pd.to_datetime(text, errors="coerce")
        if not pd.isna(parsed):
            return parsed.strftime("%H:%M:%S")

        try:
            numeric = float(text)
            if 0 <= numeric < 1:
                total_seconds = int(round(numeric * 24 * 60 * 60))
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception:
            pass

        return text

    time_text = time_series.map(_time_to_text)
    datetime_text = date_parsed.dt.strftime("%Y-%m-%d") + " " + time_text.astype(str)

    parsed_datetime = pd.to_datetime(
        datetime_text,
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce",
    )

    if parsed_datetime.notna().sum() == 0:
        parsed_datetime = pd.to_datetime(
            date_raw.astype(str).str.strip() + " " + time_raw.astype(str).str.strip(),
            dayfirst=True,
            errors="coerce",
        )

    return parsed_datetime


def prepare_common_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza campos comuns para uso pelos gráficos.
    """
    df = dataframe.copy()

    if "Data" not in df.columns or "Hora " not in df.columns:
        raise ValueError("O DataFrame processado precisa possuir as colunas 'Data' e 'Hora '.")

    df["Datetime"] = parse_datetime_columns(df)
    df["Data"] = df["Datetime"].dt.date
    df["Hora "] = df["Datetime"].dt.time

    df = df.dropna(subset=["Datetime"]).copy()
    df = df.sort_values("Datetime").reset_index(drop=True)

    for column in df.columns:
        if column in ["Data", "Hora ", "Datetime"]:
            continue

        df[column] = parse_numeric_series(df[column])

    return df

def normalize_time_value(value):
    if isinstance(value, time):
        return value

    if pd.isna(value):
        return None

    if isinstance(value, str):
        clean = value.strip().replace(",", ".")

        parsed = pd.to_datetime(clean, format="%H:%M:%S.%f", errors="coerce")
        if pd.isna(parsed):
            parsed = pd.to_datetime(clean, format="%H:%M:%S", errors="coerce")
        if pd.isna(parsed):
            parsed = pd.to_datetime(clean, errors="coerce")

        if pd.isna(parsed):
            return None

        return parsed.time()

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None

    return parsed.time()


def combine_date_time(date_value, time_value):
    if pd.isna(date_value) or time_value is None:
        return pd.NaT

    return pd.Timestamp.combine(pd.Timestamp(date_value).date(), time_value)


def infer_integration_time(dataframe: pd.DataFrame) -> int:
    if dataframe is None or dataframe.empty or "Datetime" not in dataframe.columns:
        return 0

    diffs = dataframe["Datetime"].sort_values().diff().dropna()

    if diffs.empty:
        return 0

    seconds = diffs.dt.total_seconds()
    seconds = seconds[seconds > 0]

    if seconds.empty:
        return 0

    return int(round(seconds.median()))


def infer_nominal_tension(dataframe: pd.DataFrame) -> str:
    """
    Infere a tensão nominal com tolerância a arquivos que não trazem
    tensão fase-fase válida ou que tenham colunas preenchidas com NaN/zero.
    """
    phase_phase_columns = [
        "Tensao AB (médio)(V)",
        "Tensao BC (médio)(V)",
        "Tensao CA (médio)(V)",
        "Tensão AB (médio)(V)",
        "Tensão BC (médio)(V)",
        "Tensão CA (médio)(V)",
    ]

    available = [col for col in phase_phase_columns if col in dataframe.columns]
    mean_value = pd.NA

    if available:
        values = dataframe[available].apply(pd.to_numeric, errors="coerce")
        values = values.where(values > 0)
        mean_value = values.stack().mean()

    if pd.isna(mean_value):
        phase_neutral_columns = [
            "Tensão A (médio)(V)",
            "Tensão B (médio)(V)",
            "Tensão C (médio)(V)",
        ]
        available_fn = [col for col in phase_neutral_columns if col in dataframe.columns]
        if available_fn:
            values = dataframe[available_fn].apply(pd.to_numeric, errors="coerce")
            values = values.where(values > 0)
            phase_neutral_mean = values.stack().mean()
            if not pd.isna(phase_neutral_mean):
                mean_value = float(phase_neutral_mean) * (3 ** 0.5)

    if pd.isna(mean_value):
        return "380"

    mean_value = float(mean_value)
    supported = [220, 254, 380, 440]
    nearest = min(supported, key=lambda nominal: abs(nominal - mean_value))
    return str(nearest)
