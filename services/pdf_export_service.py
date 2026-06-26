"""PDF export service boundary."""

from __future__ import annotations

from pathlib import Path

from core.pdf_exporter import (
    build_custom_pdf_filename,
    build_daily_pdf_filename,
    ensure_unique_pdf_path,
    export_figures_to_pdf,
    next_pdf_suffix_path,
    reserve_unique_pdf_paths,
)


class PdfExportService:
    def export_figures_to_pdf(self, **kwargs):
        return export_figures_to_pdf(**kwargs)

    def ensure_unique_pdf_path(self, path: Path) -> Path:
        return ensure_unique_pdf_path(path)

    def next_pdf_suffix_path(self, path: Path) -> Path:
        return next_pdf_suffix_path(path)

    def reserve_unique_pdf_paths(self, output_dir: Path, filenames: list[str]) -> list[Path]:
        return reserve_unique_pdf_paths(output_dir, filenames)

    def build_daily_pdf_filename(self, *args, **kwargs) -> str:
        return build_daily_pdf_filename(*args, **kwargs)

    def build_custom_pdf_filename(self, *args, **kwargs) -> str:
        return build_custom_pdf_filename(*args, **kwargs)

