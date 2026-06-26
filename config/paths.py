"""Centralized path resolution for development and packaged runtimes."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def get_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


def get_runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return get_project_root()


def get_assets_dir() -> Path:
    return get_project_root() / "assets"


def get_asset_path(filename: str) -> Path:
    return get_assets_dir() / filename


def get_categorized_asset_path(category: str, filename: str) -> Path:
    return get_assets_dir() / category / filename


def get_logo_asset_path(filename: str) -> Path:
    categorized = get_categorized_asset_path("logos", filename)
    if categorized.exists():
        return categorized
    return get_asset_path(filename)


def get_icon_asset_path(filename: str) -> Path:
    categorized = get_categorized_asset_path("icons", filename)
    if categorized.exists():
        return categorized
    return get_asset_path(filename)


def get_user_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "MUG"
    return Path.home() / "AppData" / "Local" / "MUG"


def get_logs_dir() -> Path:
    preferred = get_user_data_dir() / "logs"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "MUG" / "logs"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def get_version_file_candidates() -> tuple[Path, ...]:
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        internal_dir = Path(getattr(sys, "_MEIPASS", executable_dir)).resolve()
        return (
            executable_dir / "VERSION",
            internal_dir / "VERSION",
        )
    return (get_project_root() / "VERSION",)

