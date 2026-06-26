import os
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class FakeErrorService:
    def log_exception(self, *args, **kwargs):
        pass


class FakeMeasurementValidationService:
    def __init__(self, result):
        self.result = result
        self.paths = []

    def validate(self, path):
        self.paths.append(Path(path))
        return self.result


class FakeContainer:
    def __init__(self, result):
        self.assets = None
        self.error_service = FakeErrorService()
        self.measurement_validation_service = FakeMeasurementValidationService(result)


class FakeMainWindow:
    available_update = None


def test_input_page_guides_measurement_selection_before_generation():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWidgets import QFrame
    from domain.measurement_validation import STATUS_VALID, MeasurementValidationResult
    from ui.input_page import InputPage

    app = QApplication.instance() or QApplication([])
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
    container = FakeContainer(result)
    page = InputPage(FakeMainWindow(), service_container=container)

    assert page.revision_input["input"].text() == "00"
    assert not page.generate_button.isEnabled()
    assert page.measurement_step_title.text() == "ETAPA 1 - SELECIONAR MEDIÇÃO"
    assert "Selecione ou arraste" in page.measurement_step_subtitle.text()
    assert len(page.findChildren(QFrame, "referenceImageCard")) == 2

    page.handle_selected_file(Path("measurement.txt"))
    for _ in range(4):
        app.processEvents()

    assert container.measurement_validation_service.paths == [Path("measurement.txt")]
    assert page.measurement_validation is result
    assert page.generate_button.isEnabled()
    assert page.drop_zone._detail_rows["Status"][1].text() == "Arquivo válido"
    page.close()
    page.deleteLater()
    app.processEvents()
