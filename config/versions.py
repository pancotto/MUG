"""Centralized application version helpers."""

from __future__ import annotations

from config.paths import get_version_file_candidates


APP_VERSION_FALLBACK = "1.6.0"


def get_app_version(fallback: str = APP_VERSION_FALLBACK) -> str:
    for version_file in get_version_file_candidates():
        try:
            if version_file.exists():
                version = version_file.read_text(encoding="utf-8").strip()
                if version:
                    return version
        except OSError:
            continue
    return fallback


def format_app_version(version: str) -> str:
    clean = str(version or "").strip()
    if clean.lower().startswith("v"):
        return f"v{clean[1:]}"
    return f"v{clean}"


def version_without_v(version: str) -> str:
    clean = str(version or "").strip()
    if clean.lower().startswith("v"):
        return clean[1:]
    return clean
