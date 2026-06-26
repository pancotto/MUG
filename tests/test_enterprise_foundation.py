from pathlib import Path

from domain.input_rules import (
    AnalysisInputValues,
    build_input_data,
    normalize_analysis_values,
    validate_analysis_values,
)
from infrastructure.event_bus import EventBus
from services.container import create_service_container


def test_service_container_is_lazy_for_heavy_services():
    container = create_service_container()

    assert container.event_bus is not None
    assert container.error_service is not None
    assert container._instances == {}


def test_service_container_exposes_lightweight_measurement_validation_service():
    container = create_service_container()

    service = container.measurement_validation_service

    assert service is container.measurement_validation_service
    assert "measurement_validation_service" in container._instances


def test_event_bus_publishes_to_subscribers():
    bus = EventBus()
    received = []

    bus.subscribe("analysis.ready", received.append)
    bus.publish("analysis.ready", rows=10)

    assert len(received) == 1
    assert received[0].name == "analysis.ready"
    assert received[0].payload == {"rows": 10}


def test_domain_input_rules_preserve_normalization_and_messages(tmp_path):
    values = AnalysisInputValues(
        company=" ecocel ",
        city=" vitoria/es ",
        equipment_type="trafo",
        equipment_reference=" trafo 01 ",
        equipment_value="500,5",
        local=" lado fonte ",
        revision="00",
        selected_path=tmp_path / "medicao.txt",
    )

    normalized = normalize_analysis_values(values)

    assert normalized.company == "ECOCEL"
    assert normalized.city == "VITORIA/ES"
    assert normalized.equipment_reference == "TRAFO 01"
    assert normalized.equipment_value == "500.5"
    assert validate_analysis_values(values) == (True, "")

    input_data = build_input_data(values)
    assert input_data.company == "ECOCEL"
    assert input_data.excel_path == Path(tmp_path / "medicao.txt")


def test_domain_input_rules_reject_missing_file_with_existing_message():
    values = AnalysisInputValues(
        company="ECOCEL",
        city="VITORIA/ES",
        equipment_type="TRAFO",
        equipment_reference="TRAFO 01",
        equipment_value="500",
        local="LADO FONTE",
        revision="00",
        selected_path=None,
    )

    assert validate_analysis_values(values) == (False, "Selecione o arquivo de dados.")


def test_domain_input_rules_reject_invalid_measurement_validation(tmp_path):
    values = AnalysisInputValues(
        company="ECOCEL",
        city="VITORIA/ES",
        equipment_type="TRAFO",
        equipment_reference="TRAFO 01",
        equipment_value="500",
        local="LADO FONTE",
        revision="00",
        selected_path=tmp_path / "medicao.txt",
        measurement_is_valid=False,
    )

    assert validate_analysis_values(values) == (
        False,
        "Selecione um arquivo de medição válido.",
    )
