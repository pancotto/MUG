from pathlib import Path

import pandas as pd
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication

from core.models import EQUIPMENT_TYPE_BREAKER, ProcessedData
from ui.graph_page import ExportTitleCustomizationPanel


def ensure_qapplication():
    return QApplication.instance() or QApplication([])


def validator_state(field, value: str):
    state, _, _ = field.validator().validate(value, 0)
    return state


def test_display_equipment_metadata_does_not_change_nominal_calculation():
    processed = ProcessedData(
        company="ORIGINAL",
        city="VITORIA",
        trafo=263.27,
        local="QDF",
        revision="00",
        excel_path=Path("measurement.txt"),
        dataframe=pd.DataFrame({"Datetime": []}),
        integration_time=10,
        tension="380",
        equipment_type=EQUIPMENT_TYPE_BREAKER,
        equipment_reference="DJ ORIGINAL",
        equipment_value=400,
    )
    original_current = processed.nominal_current_a

    processed.display_equipment_reference = "DJ AR COND"
    processed.display_equipment_value = "250"
    processed.display_integration_text = "10 minutos"

    assert processed.equipment_description() == "DJ AR COND 250A"
    assert processed.integration_display_text() == "10 minutos"
    assert processed.integration_time == 10
    assert processed.nominal_current_a == original_current


def test_default_integration_display_uses_technical_interval():
    processed = ProcessedData(
        company="ORIGINAL",
        city="VITORIA",
        trafo=500,
        local="QDF",
        revision="00",
        excel_path=Path("measurement.txt"),
        dataframe=pd.DataFrame({"Datetime": []}),
        integration_time=15,
        tension="380",
    )

    assert processed.integration_display_text() == "15s"


def test_title_panel_preserves_breaker_display_values():
    ensure_qapplication()
    processed = ProcessedData(
        company="PICPAY",
        city="VITORIA/ES",
        trafo=263.27,
        local="QDF-BB",
        revision="00",
        excel_path=Path("measurement.txt"),
        dataframe=pd.DataFrame({"Datetime": []}),
        integration_time=15,
        tension="380",
        equipment_type=EQUIPMENT_TYPE_BREAKER,
        equipment_reference="DJ GERAL",
        equipment_value=400,
    )
    panel = ExportTitleCustomizationPanel()

    panel.refresh_context(processed)

    assert panel.fields["equipment_value"].text() == "400"
    assert panel.fields["local"].text() == "QDF-BB"
    assert panel.fields["equipment_reference"].text() == "DJ GERAL"
    assert panel.equipment_value_label.text() == "Corrente (A)"


def test_title_panel_uses_transformer_power_label():
    ensure_qapplication()
    processed = ProcessedData(
        company="PICPAY",
        city="VITORIA/ES",
        trafo=500,
        local="QDF-BB",
        revision="00",
        excel_path=Path("measurement.txt"),
        dataframe=pd.DataFrame({"Datetime": []}),
        integration_time=15,
        tension="380",
        equipment_reference="TRAFO 01",
        equipment_value=500,
    )
    panel = ExportTitleCustomizationPanel()

    panel.refresh_context(processed)

    assert panel.fields["equipment_value"].text() == "500"
    assert panel.equipment_value_label.text() == "Potência (kVA)"


def test_title_panel_switching_no_restores_original_values():
    ensure_qapplication()
    processed = ProcessedData(
        company="PICPAY",
        city="VITORIA/ES",
        trafo=500,
        local="QDF-BB",
        revision="00",
        excel_path=Path("measurement.txt"),
        dataframe=pd.DataFrame({"Datetime": []}),
        integration_time=15,
        tension="380",
        equipment_reference="TRAFO 01",
        equipment_value=500,
    )
    panel = ExportTitleCustomizationPanel()
    panel.refresh_context(processed)

    panel.yes_radio.setChecked(True)
    panel.fields["local"].setText("QGBT")
    panel.fields["display_integration_text"].setText("10 minutos")
    panel.no_radio.setChecked(True)

    assert panel.fields["local"].text() == "QDF-BB"
    assert panel.fields["display_integration_text"].text() == "15s"


def test_title_panel_text_fields_auto_uppercase_while_typing():
    ensure_qapplication()
    panel = ExportTitleCustomizationPanel()
    panel.yes_radio.setChecked(True)

    examples = {
        "company": ("picpay", "PICPAY"),
        "city": ("vitória/es", "VITÓRIA/ES"),
        "local": ("qdf-bb (ar cond.)", "QDF-BB (AR COND.)"),
        "equipment_reference": ("dj geral", "DJ GERAL"),
    }

    for key, (typed_text, expected_text) in examples.items():
        field = panel.fields[key]
        field.setText(typed_text)
        field.textEdited.emit(typed_text)
        assert field.text() == expected_text


def test_title_panel_revision_is_digits_only():
    ensure_qapplication()
    panel = ExportTitleCustomizationPanel()
    field = panel.fields["revision"]

    assert validator_state(field, "00") == QValidator.State.Acceptable
    assert validator_state(field, "1A") == QValidator.State.Invalid
    assert validator_state(field, "REV00") == QValidator.State.Invalid


def test_title_panel_equipment_value_is_numeric_only():
    ensure_qapplication()
    panel = ExportTitleCustomizationPanel()
    field = panel.fields["equipment_value"]

    assert validator_state(field, "400") == QValidator.State.Acceptable
    assert validator_state(field, "400,5") == QValidator.State.Acceptable
    assert validator_state(field, "400.5") == QValidator.State.Acceptable
    assert validator_state(field, "400A") == QValidator.State.Invalid
    assert validator_state(field, "abc") == QValidator.State.Invalid


def test_title_panel_integration_text_remains_flexible_and_display_only():
    ensure_qapplication()
    processed = ProcessedData(
        company="PICPAY",
        city="VITORIA/ES",
        trafo=500,
        local="QDF-BB",
        revision="00",
        excel_path=Path("measurement.txt"),
        dataframe=pd.DataFrame({"Datetime": []}),
        integration_time=15,
        tension="380",
        equipment_reference="TRAFO 01",
        equipment_value=500,
    )
    original_integration_time = processed.integration_time
    panel = ExportTitleCustomizationPanel()
    panel.refresh_context(processed)
    panel.yes_radio.setChecked(True)

    field = panel.fields["display_integration_text"]
    for value in ("1s", "5s", "10s", "15s", "10min"):
        field.setText(value)
        assert field.text() == value
        assert field.validator() is None
        assert panel.metadata()["display_integration_text"] == value
        assert processed.integration_time == original_integration_time
