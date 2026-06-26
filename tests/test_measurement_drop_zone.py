import os
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_measurement_drop_zone_is_accessible_and_keyboard_selectable():
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    from ui.measurement_drop_zone import MeasurementDropZone

    app = QApplication.instance() or QApplication([])
    zone = MeasurementDropZone()
    received = []
    zone.open_file_requested.connect(lambda: received.append("open"))

    assert zone.acceptDrops()
    assert zone.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert "seleção da medição" in zone.accessibleName()

    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier,
    )
    zone.keyPressEvent(event)

    assert received == ["open"]
    zone.close()
    zone.deleteLater()
    app.processEvents()


def test_measurement_drop_zone_displays_validation_result():
    from PySide6.QtWidgets import QApplication
    from domain.measurement_validation import STATUS_VALID, MeasurementValidationResult
    from ui.measurement_drop_zone import MeasurementDropZone

    app = QApplication.instance() or QApplication([])
    zone = MeasurementDropZone()
    result = MeasurementValidationResult(
        path=Path("measurement.txt"),
        status=STATUS_VALID,
        manufacturer="Primata P55",
        file_type="TXT",
        period="01/01/2026 00:00:00 - 01/01/2026 00:15:00",
        integration_interval="15 min",
        records=2,
        message="Medição carregada com sucesso.",
    )

    zone.set_validation_result(result)

    assert "Medição carregada com sucesso" in zone.primary_label.text()
    assert not zone.details_widget.isHidden()
    assert zone._detail_rows["Status"][1].text() == "Arquivo válido"
    zone.close()
    zone.deleteLater()
    app.processEvents()


def test_measurement_drop_zone_displays_invalid_recovery_state():
    from PySide6.QtWidgets import QApplication
    from domain.measurement_validation import STATUS_UNSUPPORTED, MeasurementValidationResult
    from ui.measurement_drop_zone import MeasurementDropZone

    app = QApplication.instance() or QApplication([])
    zone = MeasurementDropZone()
    result = MeasurementValidationResult(
        path=Path("measurement.csv"),
        status=STATUS_UNSUPPORTED,
        file_type="CSV",
        message="Use arquivos .txt ou .xlsx.",
    )

    zone.set_validation_result(result)

    assert "Arquivo inválido" in zone.primary_label.text()
    assert "Use arquivos .txt ou .xlsx." in zone.secondary_label.text()
    assert zone.details_widget.isHidden()
    assert not zone.replace_button.isHidden()
    assert zone.replace_button.text() == "Selecionar outra medição"
    zone.close()
    zone.deleteLater()
    app.processEvents()
