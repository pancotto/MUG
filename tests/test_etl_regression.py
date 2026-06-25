from pathlib import Path

import pandas as pd
import pytest

from core.excel_reader import process_input_data
from core.models import EQUIPMENT_TYPE_TRAFO, InputData


ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "benchmarks" / "datasets"


COMMON_ELECTRICAL_COLUMNS = [
    "Tensão A (médio)(V)",
    "Corrente A (médio)(A)",
    "Pot Ativa Cons. Trifásica Cons. (médio)(kW)",
    "Pot Aparente Trifásica (médio)(kVA)",
    "FP Trifásico (médio)(%)",
    "DHT VA (médio)(%)",
]


def benchmark_dataset_cases():
    cases = [
        (
            "primata.txt",
            {
                "rows": 33603,
                "columns": 65,
                "integration_time": 15,
                "tension": "220",
                "start": "2026-01-27 15:00:00",
                "end": "2026-02-02 11:00:30",
            },
        ),
        (
            "embrasul.txt",
            {
                "rows": 15044,
                "columns": 71,
                "integration_time": 10,
                "tension": "380",
                "start": "2026-04-16 08:30:05",
                "end": "2026-04-18 02:17:17",
            },
        ),
    ]

    if (DATASETS / "primata.xlsx").exists():
        cases.append(
            (
                "primata.xlsx",
                {
                    "rows": 33603,
                    "columns": 65,
                    "integration_time": 15,
                    "tension": "220",
                    "start": "2026-01-27 15:00:00",
                    "end": "2026-02-02 11:00:30",
                },
            )
        )

    return cases


def input_data_for(path: Path) -> InputData:
    return InputData(
        company="ASD",
        city="VITORIA/ES",
        equipment_type=EQUIPMENT_TYPE_TRAFO,
        equipment_reference="TR-01",
        equipment_value=500.0,
        local="BENCHMARK",
        revision="00",
        excel_path=path,
    )


@pytest.mark.parametrize("filename, expected", benchmark_dataset_cases())
def test_process_input_data_regression_for_supported_datasets(filename, expected):
    dataset_path = DATASETS / filename
    assert dataset_path.exists(), f"missing benchmark dataset: {dataset_path}"

    processed = process_input_data(input_data_for(dataset_path))
    dataframe = processed.dataframe

    assert len(dataframe) == expected["rows"]
    assert len(dataframe.columns) == expected["columns"]
    assert processed.integration_time == expected["integration_time"]
    assert processed.tension == expected["tension"]
    assert processed.company == "ASD"
    assert processed.city == "VITORIA/ES"
    assert processed.local == "BENCHMARK"
    assert processed.revision == "00"
    assert processed.equipment_type == EQUIPMENT_TYPE_TRAFO
    assert processed.equipment_reference == "TR-01"
    assert processed.equipment_value == 500.0
    assert processed.excel_path == dataset_path

    assert "Datetime" in dataframe.columns
    assert pd.api.types.is_datetime64_any_dtype(dataframe["Datetime"])
    assert dataframe["Datetime"].notna().all()
    assert dataframe["Datetime"].is_monotonic_increasing
    assert dataframe["Datetime"].min() == pd.Timestamp(expected["start"])
    assert dataframe["Datetime"].max() == pd.Timestamp(expected["end"])

    for column in COMMON_ELECTRICAL_COLUMNS:
        assert column in dataframe.columns
        values = pd.to_numeric(dataframe[column], errors="coerce")
        assert values.notna().any(), f"{filename}: {column} is empty"
        assert values.abs().sum() > 0, f"{filename}: {column} has no signal"
