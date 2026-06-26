from pathlib import Path

import pytest

from domain.measurement_validation import (
    STATUS_CORRUPTED,
    STATUS_UNSUPPORTED,
    STATUS_VALID,
)
from services.measurement_validation_service import MeasurementValidationService


ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "benchmarks" / "datasets"


def test_measurement_validation_detects_primata_txt_metadata():
    result = MeasurementValidationService().validate(DATASETS / "primata.txt")

    assert result.status == STATUS_VALID
    assert result.is_valid
    assert result.manufacturer == "Primata P55"
    assert result.file_type == "TXT"
    assert result.records == 33603
    assert result.integration_interval == "15 s"
    assert "27/01/2026 15:00:00" in result.period
    assert "02/02/2026 11:00:30" in result.period


def test_measurement_validation_detects_embrasul_txt_metadata():
    result = MeasurementValidationService().validate(DATASETS / "embrasul.txt")

    assert result.status == STATUS_VALID
    assert result.is_valid
    assert result.manufacturer == "Embrasul RE7080"
    assert result.file_type == "TXT"
    assert result.records == 15044
    assert result.integration_interval == "10 s"
    assert "16/04/2026 08:30:05" in result.period
    assert "18/04/2026 02:17:17" in result.period


@pytest.mark.skipif(
    not (DATASETS / "primata.xlsx").exists(),
    reason="Primata XLSX benchmark fixture is optional",
)
def test_measurement_validation_detects_primata_xlsx_metadata():
    result = MeasurementValidationService().validate(DATASETS / "primata.xlsx")

    assert result.status == STATUS_VALID
    assert result.is_valid
    assert result.manufacturer == "Primata P55"
    assert result.file_type == "XLSX"
    assert result.records == 33603
    assert result.integration_interval == "15 s"


def test_measurement_validation_rejects_unsupported_format(tmp_path):
    unsupported = tmp_path / "measurement.csv"
    unsupported.write_text("DATA,HORA\n", encoding="utf-8")

    result = MeasurementValidationService().validate(unsupported)

    assert result.status == STATUS_UNSUPPORTED
    assert not result.is_valid
    assert result.status_label == "Formato não suportado"


def test_measurement_validation_reports_corrupted_xlsx(tmp_path):
    corrupted = tmp_path / "measurement.xlsx"
    corrupted.write_text("not a workbook", encoding="utf-8")

    result = MeasurementValidationService().validate(corrupted)

    assert result.status == STATUS_CORRUPTED
    assert not result.is_valid
