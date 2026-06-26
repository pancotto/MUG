"""Update-check service boundary."""

from __future__ import annotations

from core.update_checker import UpdateChecker


class UpdateService:
    def is_update_available(self, current_version: str):
        return UpdateChecker.is_update_available(current_version)

    def get_direct_download_url(self, update: dict) -> str:
        return UpdateChecker.get_direct_download_url(update)

    def get_release_page_url(self, update: dict) -> str:
        return UpdateChecker.get_release_page_url(update)

