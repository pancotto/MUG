from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pandas as pd


@dataclass
class InputData:
    """
    Dados informados pelo usuário na tela inicial.
    """
    company: str
    city: str
    trafo: float
    local: str
    revision: str
    excel_path: Path


@dataclass
class ProcessedData:
    """
    Dados já processados a partir do arquivo Excel.
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


@dataclass
class AppAssets:
    """
    Caminhos dos arquivos de apoio visual da aplicação.
    """
    primata_logo: Optional[Path] = None
    primata_cola: Optional[Path] = None
    logo: Optional[Path] = None