from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_startup_failure_shows_friendly_dialog_without_traceback():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "QMessageBox.critical" in source
    assert '"MUG could not start"' in source
    assert "_startup_failure_message(services.error_service)" in source
    assert "traceback" not in source.lower()
    assert "services.error_service.log_exception(exc, \"Main window startup failed\")" in source


def test_graph_loading_reports_success_or_failure_before_navigation():
    main_window = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
    input_page = (ROOT / "ui" / "input_page.py").read_text(encoding="utf-8")
    graph_page = (ROOT / "ui" / "graph_page.py").read_text(encoding="utf-8")

    assert "if not self.graph_page.load_processed_data(processed):" in main_window
    assert "return False" in main_window
    assert "return True" in main_window
    assert "if not self.main_window.set_processed_data(processed):" in input_page
    assert "self.main_window.show_graph_page()" in input_page
    assert "def load_processed_data(self, processed: ProcessedData) -> bool:" in graph_page
    assert "self.clear_loaded_data()" in graph_page
    assert "return False" in graph_page
    assert "return True" in graph_page


def test_update_active_interval_has_safe_unavailable_state():
    source = (ROOT / "ui" / "graph_page.py").read_text(encoding="utf-8")

    assert "start = None" in source
    assert "end = None" in source
    assert '"Período indisponível"' in source
    assert "Failed to update active full-measurement interval" in source


def test_error_service_provides_friendly_recovery_messages():
    from services.error_service import ErrorService

    service = ErrorService()

    assert "arquivo é válido" in service.friendly_processing_message()
    assert "gráficos não puderam ser montados" in service.friendly_graph_rendering_message()
    assert "datas e horários" in service.friendly_filter_message()
    assert "zoom" in service.friendly_zoom_message()
    assert "log" in service.friendly_export_message()


def test_pdf_cancellation_feedback_is_best_effort_and_clear():
    source = (ROOT / "ui" / "graph_page.py").read_text(encoding="utf-8")

    assert "Cancelando após concluir o PDF atual..." in source
    assert "request_cancel()" in source
    assert "self.cancel_standard_button.setEnabled(False)" in source
    assert "self.cancel_daily_button.setEnabled(False)" in source


def test_update_prompt_dismissal_is_session_scoped():
    source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")

    assert "self._dismissed_update_versions: set[str] = set()" in source
    assert "update_version in self._dismissed_update_versions" in source
    assert "self._dismissed_update_versions.add(update_version)" in source
    assert "self.available_update = None" in source


def test_graph_html_uses_session_temp_directory_with_cleanup():
    source = (ROOT / "ui" / "graph_page.py").read_text(encoding="utf-8")

    assert 'tempfile.mkdtemp(prefix="mug_graph_html_")' in source
    assert "self._graph_html_dir /" in source
    assert "cleanup_temporary_graph_html" in source
    assert "shutil.rmtree(temp_dir, ignore_errors=True)" in source
    assert "Path(tempfile.gettempdir()) /" not in source


def test_unsupported_drop_feedback_is_explicit_and_does_not_emit_file():
    source = (ROOT / "ui" / "measurement_drop_zone.py").read_text(encoding="utf-8")

    assert "Formato não suportado. Selecione um arquivo .xlsx ou .txt compatível." in source
    assert "event.ignore()" in source
    assert "self.file_dropped.emit(path)" in source
