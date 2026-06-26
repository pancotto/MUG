from config.paths import (
    get_asset_path,
    get_assets_dir,
    get_logo_asset_path,
    get_project_root,
)
from core.models import AppAssets


def get_app_assets() -> AppAssets:
    """
    Retorna os caminhos padronizados dos assets da aplicação.
    """
    return AppAssets(
        primata_logo=get_logo_asset_path("primata_logo.png"),
        primata_cola=get_asset_path("primata_cola.png"),
        embrasul_logo=get_logo_asset_path("embrasul_logo.png"),
        embrasul_cola=get_asset_path("embrasul_cola.png"),
        logo=get_logo_asset_path("logo.png"),
    )
