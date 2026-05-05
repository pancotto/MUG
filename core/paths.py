import sys
from pathlib import Path

from core.models import AppAssets


def get_project_root() -> Path:
    """
    Retorna a raiz do projeto em desenvolvimento
    ou a raiz temporária criada pelo PyInstaller.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_assets_dir() -> Path:
    """
    Retorna a pasta de assets.
    """
    return get_project_root() / "assets"


def get_asset_path(filename: str) -> Path:
    """
    Retorna o caminho completo de um asset.
    """
    return get_assets_dir() / filename


def get_app_assets() -> AppAssets:
    """
    Retorna os caminhos padronizados dos assets da aplicação.
    """
    return AppAssets(
        primata_logo=get_asset_path("primata_logo.png"),
        primata_cola=get_asset_path("primata_cola.png"),
        logo=get_asset_path("logo.png"),
    )