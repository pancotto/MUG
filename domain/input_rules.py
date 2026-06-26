"""Domain-level rules for creating a measurement analysis request."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.models import InputData


@dataclass(frozen=True)
class AnalysisInputValues:
    company: str
    city: str
    equipment_type: str
    equipment_reference: str
    equipment_value: str
    local: str
    revision: str
    selected_path: Path | None


def normalize_analysis_values(values: AnalysisInputValues) -> AnalysisInputValues:
    return AnalysisInputValues(
        company=values.company.strip().upper(),
        city=values.city.strip().upper(),
        equipment_type=values.equipment_type.strip().upper(),
        equipment_reference=values.equipment_reference.strip().upper(),
        equipment_value=values.equipment_value.strip().replace(",", "."),
        local=values.local.strip().upper(),
        revision=values.revision.strip(),
        selected_path=values.selected_path,
    )


def validate_analysis_values(values: AnalysisInputValues) -> tuple[bool, str]:
    values = normalize_analysis_values(values)

    if not values.company:
        return False, "Informe a EMPRESA."
    if not values.city:
        return False, "Informe a CIDADE/ES."
    if not values.equipment_reference:
        return False, "Informe a REFERÊNCIA / TAG do equipamento."
    if not values.equipment_value:
        if values.equipment_type == "TRAFO":
            return False, "Informe a POTÊNCIA do transformador."
        return False, "Informe a CORRENTE do disjuntor."
    if not values.local:
        return False, "Informe o LOCAL."
    if not values.revision:
        return False, "Informe a REVISÃO."
    if values.selected_path is None:
        return False, "Selecione o arquivo de dados."
    if values.selected_path.suffix.lower() not in [".xlsx", ".txt"]:
        return False, "O arquivo selecionado deve ser .xlsx ou .txt."

    try:
        numeric_equipment_value = float(values.equipment_value)
    except ValueError:
        if values.equipment_type == "TRAFO":
            return False, "O campo POTÊNCIA deve ser numérico."
        return False, "O campo CORRENTE deve ser numérico."

    if numeric_equipment_value <= 0:
        if values.equipment_type == "TRAFO":
            return False, "A POTÊNCIA deve ser maior que zero."
        return False, "A CORRENTE deve ser maior que zero."

    if not values.revision.isdigit():
        return False, "O campo REVISÃO deve conter apenas números."

    return True, ""


def build_input_data(values: AnalysisInputValues) -> InputData:
    values = normalize_analysis_values(values)
    if values.selected_path is None:
        raise ValueError("Selecione o arquivo de dados.")
    return InputData(
        company=values.company,
        city=values.city,
        equipment_type=values.equipment_type,
        equipment_reference=values.equipment_reference,
        equipment_value=float(values.equipment_value),
        local=values.local,
        revision=values.revision,
        excel_path=values.selected_path,
    )

