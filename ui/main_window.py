from PySide6.QtCore import QObject, QTimer, QThread, Qt, Signal, Slot
import webbrowser

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox

from config.application import APP_DISPLAY_NAME
from config.constants import UPDATE_CHECK_STARTUP_DELAY_MS
from config.versions import format_app_version, get_app_version
from services.container import get_service_container
from ui.input_page import InputPage
from ui.graph_page import GraphPage
from ui.about_dialog import AboutDialog


class UpdateCheckWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, current_version: str, update_service=None):
        super().__init__()
        self.current_version = current_version
        self.update_service = update_service or get_service_container().update_service

    @Slot()
    def run(self):
        try:
            self.finished.emit(self.update_service.is_update_available(self.current_version))
        except Exception as exc:
            self.error.emit(str(exc))
            self.finished.emit(None)


class MainWindow(QMainWindow):
    """
    Janela principal da aplicação desktop.
    """

    def __init__(self, service_container=None):
        super().__init__()

        self.services = service_container or get_service_container()
        self.processed_data = None

        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(1400, 900)
        self.setMinimumSize(1180, 760)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.input_page = InputPage(self, service_container=self.services)
        self.graph_page = GraphPage(self, service_container=self.services)

        self.stack.addWidget(self.input_page)
        self.stack.addWidget(self.graph_page)

        self.show_input_page()

        self.available_update = None
        self._dismissed_update_versions: set[str] = set()
        self._update_thread: QThread | None = None
        self._update_worker: UpdateCheckWorker | None = None

        self.schedule_update_check()

    def set_processed_data(self, processed):
        if not self.graph_page.load_processed_data(processed):
            self.processed_data = None
            return False
        self.processed_data = processed
        self.services.event_bus.publish("analysis.processed", processed=processed)
        return True

    def start_new_analysis(self):

        msg_box = QMessageBox(self)

        msg_box.setWindowTitle("Nova análise")

        msg_box.setText(
            "Deseja iniciar uma nova análise?\n\n"
            "Os gráficos atuais serão descartados."
        )

        sim_button = msg_box.addButton(
            "SIM",
            QMessageBox.ButtonRole.YesRole
        )

        nao_button = msg_box.addButton(
            "NÃO",
            QMessageBox.ButtonRole.NoRole
        )

        msg_box.setDefaultButton(nao_button)

        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #111111;
                color: #f1f1f1;
            }

            QLabel {
                color: #f1f1f1;
                font-size: 12px;
            }
        """)

        sim_button.setStyleSheet("""
            QPushButton {
                background-color: #2d7d46;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 18px;
                min-width: 110px;
                font-weight: bold;
                text-align: center;
            }

            QPushButton:hover {
                background-color: #25673a;
            }
        """)

        nao_button.setStyleSheet("""
            QPushButton {
                background-color: #8b1e1e;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 18px;
                min-width: 110px;
                font-weight: bold;
                text-align: center;
            }

            QPushButton:hover {
                background-color: #a32626;
            }
        """)

        msg_box.layout().setSpacing(12)

        msg_box.exec()

        if msg_box.clickedButton() != sim_button:
            return

        self.processed_data = None
        self.services.event_bus.publish("analysis.reset")

        self.graph_page.clear_loaded_data()

        self.show_input_page()

        self.available_update = None

        self.schedule_update_check()

    def show_input_page(self):
        self.stack.setCurrentWidget(self.input_page)

    def show_graph_page(self):

        if self.processed_data is None:
            return

        self.stack.setCurrentWidget(self.graph_page)

    def schedule_update_check(self):
        QTimer.singleShot(UPDATE_CHECK_STARTUP_DELAY_MS, self.check_for_updates)

    def check_for_updates(self):
        if self._update_thread is not None:
            return

        try:
            current_version = get_app_version()

            self._update_thread = QThread(self)
            self._update_worker = UpdateCheckWorker(
                current_version,
                self.services.update_service,
            )
            self._update_worker.moveToThread(self._update_thread)

            self._update_thread.started.connect(self._update_worker.run)
            self._update_worker.finished.connect(self._update_thread.quit)
            self._update_worker.finished.connect(self._handle_update_check_finished)
            self._update_worker.error.connect(self._handle_update_check_error)
            self._update_thread.finished.connect(self._update_worker.deleteLater)
            self._update_thread.finished.connect(self._update_thread.deleteLater)
            self._update_thread.finished.connect(self._clear_update_thread_refs)

            self._update_thread.start()

        except Exception as e:

            self.services.error_service.log_exception(e, "Update check startup failed")

    @Slot(object)
    def _handle_update_check_finished(self, update):
        self.available_update = update

        if not update:
            return

        current_version = get_app_version()
        update_version = str(update.get("version") or "").strip()
        if update_version in self._dismissed_update_versions:
            return

        message = (
            f"Nova versão disponível!\n\n"
            f"Versão atual: {format_app_version(current_version)}\n"
            f"Nova versão: {format_app_version(update_version)}\n\n"
            f"Deseja baixar o instalador da nova versão?"
        )

        msg_box = QMessageBox(self)

        msg_box.setWindowTitle("Atualização disponível")

        msg_box.setText(message)

        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #111111;
                color: #f1f1f1;
            }

            QLabel {
                color: #f1f1f1;
                font-size: 12px;
            }
        """)

        yes_button = msg_box.addButton(
            "BAIXAR",
            QMessageBox.ButtonRole.YesRole
        )

        no_button = msg_box.addButton(
            "IGNORAR",
            QMessageBox.ButtonRole.NoRole
        )

        yes_button.setStyleSheet("""
            QPushButton {
                background-color: #2d7d46;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 18px;
                min-width: 110px;
                font-weight: bold;
                text-align: center;
            }

            QPushButton:hover {
                background-color: #25673a;
            }
        """)

        no_button.setStyleSheet("""
            QPushButton {
                background-color: #8b1e1e;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 18px;
                min-width: 110px;
                font-weight: bold;
                text-align: center;
            }

            QPushButton:hover {
                background-color: #a32626;
            }
        """)

        msg_box.layout().setSpacing(12)

        msg_box.exec()

        if msg_box.clickedButton() == yes_button:

            self.open_update_download(update)
        elif update_version:
            self._dismissed_update_versions.add(update_version)

    @Slot(str)
    def _handle_update_check_error(self, message: str):
        self.services.error_service.log_exception(
            RuntimeError(message),
            "Update check failed",
        )

    @Slot()
    def _clear_update_thread_refs(self):
        self._update_thread = None
        self._update_worker = None

    def open_update_download(self, update: dict):
        direct_url = str(update.get("browser_download_url") or "").strip()
        if not direct_url:
            direct_url = self.services.update_service.get_direct_download_url(update)
        release_url = self.services.update_service.get_release_page_url(update)
        target_url = direct_url or release_url

        if not target_url:
            QMessageBox.warning(
                self,
                "Atualização indisponível",
                "Não foi possível localizar um link válido para download da atualização."
            )
            self.services.error_service.log_exception(
                RuntimeError("No valid update URL available."),
                "Update download failed",
            )
            return

        try:
            opened = webbrowser.open(target_url)
            if opened:
                return
        except Exception as e:
            self.services.error_service.log_exception(e, "Failed to open update URL")

        if direct_url and release_url and direct_url != release_url:
            try:
                webbrowser.open(release_url)
                return
            except Exception as e:
                self.services.error_service.log_exception(e, "Failed to open release page URL")

        QMessageBox.warning(
            self,
            "Atualização indisponível",
            "Não foi possível abrir o link de download da atualização."
        )
