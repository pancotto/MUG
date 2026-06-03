import pandas as pd

from core.pdf_exporter import build_daily_pdf_filename


def test_build_daily_pdf_filename_uses_company_and_compact_date():
    assert (
        build_daily_pdf_filename("Ecocel", pd.Timestamp("2026-06-03"))
        == "GR - ECOCEL - 20260603.pdf"
    )


def test_build_daily_pdf_filename_sanitizes_windows_invalid_characters():
    assert (
        build_daily_pdf_filename("Eco/Cel: Unidade * 01", "2026-06-03")
        == "GR - ECO-CEL- UNIDADE - 01 - 20260603.pdf"
    )


def test_build_daily_pdf_filename_uses_fallback_company():
    assert (
        build_daily_pdf_filename("", "2026-06-03")
        == "GR - MEDICAO - 20260603.pdf"
    )
