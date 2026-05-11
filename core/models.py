from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import math

import pandas as pd


EQUIPMENT_TYPE_TRAFO = "TRAFO"
EQUIPMENT_TYPE_BREAKER = "DISJUNTOR"


@dataclass
class InputData:
    """
    Dados informados pelo usuário na tela inicial.

    equipment_type:
        - "TRAFO": equipment_value representa potência nominal em kVA.
        - "DISJUNTOR": equipment_value representa corrente nominal em A.
    """
    company: str
    city: str
    equipment_type: str
    equipment_reference: str
    equipment_value: float
    local: str
    revision: str
    excel_path: Path

    def __post_init__(self):
        self.equipment_type = normalize_equipment_type(self.equipment_type)
        self.equipment_reference = str(self.equipment_reference).strip().upper()
        self.equipment_value = float(self.equipment_value)

    @property
    def trafo(self) -> float:
        """
        Compatibilidade com versões anteriores.
        Para transformador, representa a potência em kVA.
        Para disjuntor, não deve ser usado diretamente antes de conhecer a tensão.
        """
        return self.equipment_value


@dataclass
class ProcessedData:
    """
    Dados já processados a partir do arquivo de medição.

    O campo trafo é mantido por compatibilidade com o código existente.
    Internamente, para DISJUNTOR, ele passa a representar a potência aparente
    equivalente em kVA, calculada a partir da tensão nominal e da corrente informada.
    """
    company: str
    city: str
    trafo: float
    local: str
    revision: str
    excel_path: Path
    dataframe: pd.DataFrame
    integration_time: int
    tension: str
    equipment_type: str = EQUIPMENT_TYPE_TRAFO
    equipment_reference: str = ""
    equipment_value: float = 0.0

    def __post_init__(self):
        self.equipment_type = normalize_equipment_type(self.equipment_type)
        self.equipment_reference = str(self.equipment_reference or "").strip().upper()
        self.trafo = float(self.trafo)

        if not self.equipment_value:
            self.equipment_value = self.trafo
        else:
            self.equipment_value = float(self.equipment_value)

    @property
    def tension_float(self) -> float:
        return float(str(self.tension).replace(",", "."))

    @property
    def is_transformer(self) -> bool:
        return self.equipment_type == EQUIPMENT_TYPE_TRAFO

    @property
    def is_breaker(self) -> bool:
        return self.equipment_type == EQUIPMENT_TYPE_BREAKER

    @property
    def nominal_current_a(self) -> float:
        """
        Corrente nominal usada como referência nos gráficos.
        - TRAFO: calculada por S/(V*sqrt(3)).
        - DISJUNTOR: corrente informada pelo usuário.
        """
        if self.is_breaker:
            return float(self.equipment_value)

        return (float(self.equipment_value) * 1000.0) / (self.tension_float * math.sqrt(3))

    @property
    def nominal_apparent_power_kva(self) -> float:
        """
        Potência aparente nominal/equivalente em kVA.
        - TRAFO: potência informada pelo usuário.
        - DISJUNTOR: sqrt(3) * V * I / 1000.
        """
        if self.is_breaker:
            return (self.tension_float * float(self.equipment_value) * math.sqrt(3)) / 1000.0

        return float(self.equipment_value)

    @property
    def nominal_power_kw_limit(self) -> float:
        """
        Referência numérica mantida para gráficos de potência ativa.
        Em DISJUNTOR, utiliza a potência aparente equivalente como referência conservadora.
        """
        return self.nominal_apparent_power_kva

    def equipment_description(self) -> str:
        """
        Texto usado na segunda linha dos títulos dos gráficos.

        - TRAFO: REFERÊNCIA - POTÊNCIA kVA
        - DISJUNTOR: REFERÊNCIA - CORRENTE A

        As palavras TRANSFORMADOR e DISJUNTOR não são inseridas antes do valor,
        pois a referência/tag já identifica o equipamento para o relatório.
        """
        reference = self.equipment_reference.strip()
        value_text = format_numeric_value(self.equipment_value)

        if self.is_breaker:
            value_with_unit = f"{value_text}A"
        else:
            value_with_unit = f"{value_text}kVA"

        if reference:
            return f"{reference} {value_with_unit}"

        return value_with_unit

    def tension_display(self) -> str:
        """
        Texto de tensão exibido nos títulos.

        Mantém o valor inferido internamente para cálculo, mas exibe a tensão
        no padrão de atendimento do PRODIST Módulo 8.
        """
        tension = str(self.tension).strip().replace(",", ".")

        try:
            tension_number = float(tension)
        except ValueError:
            return f"{self.tension}V"

        if abs(tension_number - 380) < 0.5:
            return "380/220V"
        if abs(tension_number - 220) < 0.5:
            return "220/127V"

        if tension_number.is_integer():
            return f"{int(tension_number)}V"

        return f"{format_numeric_value(tension_number)}V"

    def nominal_power_annotation(self, unit: str) -> str:
        unit = unit.strip()
        value = self.nominal_power_kw_limit if unit.lower() == "kw" else self.nominal_apparent_power_kva

        if self.is_breaker:
            return f"POT. EQUIV. {value:.1f}{unit}"

        return f"POT. NOMINAL {value:.1f}{unit}"


@dataclass
class AppAssets:
    """
    Caminhos dos arquivos de apoio visual da aplicação.
    """
    primata_logo: Optional[Path] = None
    primata_cola: Optional[Path] = None
    embrasul_logo: Optional[Path] = None
    embrasul_cola: Optional[Path] = None
    logo: Optional[Path] = None


def normalize_equipment_type(equipment_type: str) -> str:
    value = str(equipment_type or "").strip().upper()

    if value in {"DISJUNTOR", "BREAKER", "DJ"}:
        return EQUIPMENT_TYPE_BREAKER

    return EQUIPMENT_TYPE_TRAFO


def format_numeric_value(value: float) -> str:
    value = float(value)

    if value.is_integer():
        return str(int(value))

    return f"{value:.2f}".rstrip("0").rstrip(".")
