from pathlib import Path

import pandas as pd

from core.pdf_exporter import (
    build_custom_pdf_filename,
    build_daily_pdf_filename,
    build_pdf_filename,
    ensure_unique_pdf_path,
    next_pdf_suffix_path,
    normalize_pdf_revision,
    reserve_unique_pdf_paths,
    sanitize_pdf_filename_part,
)


def test_build_daily_pdf_filename_uses_company_and_timestamp():
    assert (
        build_daily_pdf_filename(
            "Ecocel",
            "00",
            pd.Timestamp("2026-06-03"),
            "2026-06-05 18:40:01",
        )
        == "GR - ECOCEL - 20260603-184001 - REV00.pdf"
    )


def test_build_daily_pdf_filename_sanitizes_windows_invalid_characters():
    assert (
        build_daily_pdf_filename(
            "Eco/Cel: Unidade * 01",
            "REV01",
            "2026-06-03",
            "2026-06-05 18:40:01",
        )
        == "GR - ECO-CEL- UNIDADE - 01 - 20260603-184001 - REV01.pdf"
    )


def test_build_daily_pdf_filename_uses_fallback_company():
    assert (
        build_daily_pdf_filename("", "", "2026-06-03", "2026-06-05 18:40:01")
        == "GR - MEDICAO - 20260603-184001 - REV00.pdf"
    )


def test_build_custom_pdf_filename_uses_standard_single_pattern():
    assert (
        build_custom_pdf_filename("Ecocel", "00", "2026-06-03 14:15:16")
        == "GR - ECOCEL - 20260603-141516 - REV00.pdf"
    )


def test_build_custom_pdf_filename_uses_fallback_company():
    assert (
        build_custom_pdf_filename(None, None, "2026-06-03 14:15:16")
        == "GR - MEDICAO - 20260603-141516 - REV00.pdf"
    )


def test_build_pdf_filename_uses_canonical_pattern():
    assert (
        build_pdf_filename("Ecocel", "rev02", "20260603-182657")
        == "GR - ECOCEL - 20260603-182657 - REV02.pdf"
    )


def test_revision_normalization_does_not_duplicate_rev():
    assert normalize_pdf_revision("00") == "REV00"
    assert normalize_pdf_revision("REV00") == "REV00"
    assert normalize_pdf_revision("rev00") == "REV00"
    assert normalize_pdf_revision("REV-00") == "REV00"


def test_filename_part_sanitization_collapses_spaces_and_invalid_chars():
    assert sanitize_pdf_filename_part(" Eco  / Cel : 01 ") == "ECO - CEL - 01"


def test_ensure_unique_pdf_path_adds_suffix_when_file_exists(tmp_path):
    original = tmp_path / "GR - ECOCEL - 20260603-184001 - REV00.pdf"
    original.write_text("existing", encoding="utf-8")

    assert (
        ensure_unique_pdf_path(original).name
        == "GR - ECOCEL - 20260603-184001 - REV00 (2).pdf"
    )


def test_next_pdf_suffix_path_increments_existing_suffix():
    path = Path("GR - ECOCEL - 20260603-184001 - REV00 (2).pdf")

    assert (
        next_pdf_suffix_path(path).name
        == "GR - ECOCEL - 20260603-184001 - REV00 (3).pdf"
    )


def test_reserve_unique_pdf_paths_keeps_free_filename(tmp_path):
    filename = "GR - ECOCEL - 20260603-184001 - REV00.pdf"

    paths = reserve_unique_pdf_paths(tmp_path, [filename])

    assert paths == [tmp_path / filename]


def test_reserve_unique_pdf_paths_skips_existing_filename(tmp_path):
    filename = "GR - ECOCEL - 20260603-184001 - REV00.pdf"
    (tmp_path / filename).write_text("existing", encoding="utf-8")

    paths = reserve_unique_pdf_paths(tmp_path, [filename])

    assert paths == [tmp_path / "GR - ECOCEL - 20260603-184001 - REV00 (2).pdf"]


def test_reserve_unique_pdf_paths_increments_suffix_for_existing_chain(tmp_path):
    filename = "GR - ECOCEL - 20260603-184001 - REV00.pdf"
    (tmp_path / filename).write_text("existing", encoding="utf-8")
    (tmp_path / "GR - ECOCEL - 20260603-184001 - REV00 (2).pdf").write_text(
        "existing",
        encoding="utf-8",
    )

    paths = reserve_unique_pdf_paths(tmp_path, [filename])

    assert paths == [tmp_path / "GR - ECOCEL - 20260603-184001 - REV00 (3).pdf"]


def test_reserve_unique_pdf_paths_prevents_parallel_batch_duplicates(tmp_path):
    filename = "GR - ECOCEL - 20260603-184001 - REV00.pdf"

    paths = reserve_unique_pdf_paths(tmp_path, [filename, filename, filename])

    assert [path.name for path in paths] == [
        "GR - ECOCEL - 20260603-184001 - REV00.pdf",
        "GR - ECOCEL - 20260603-184001 - REV00 (2).pdf",
        "GR - ECOCEL - 20260603-184001 - REV00 (3).pdf",
    ]
