import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from config.application import APP_DISPLAY_NAME, APP_NAME
from config.constants import SINGLE_INSTANCE_KEY, STARTUP_MAIN_WINDOW_DELAY_MS
from config.paths import get_logs_dir
from config.versions import get_app_version
from infrastructure.logging_config import LOG_FILE_NAME, configure_logging
from infrastructure.startup import SingleInstanceGuard
from services.container import create_service_container
from ui.splash_screen import show_splash_screen


def _startup_failure_message(error_service=None) -> str:
    try:
        log_path = get_logs_dir() / LOG_FILE_NAME
        if error_service is not None:
            return error_service.friendly_startup_message(str(log_path))
    except Exception:
        pass
    if error_service is not None:
        return error_service.friendly_startup_message()
    return (
        "The application encountered an unexpected error during startup.\n\n"
        "The error has been recorded in the log.\n\n"
        "If the problem persists, contact support and provide the log file."
    )


def main():
    instance_guard = SingleInstanceGuard(SINGLE_INSTANCE_KEY)
    if not instance_guard.acquire():
        return 0

    logger = configure_logging()
    services = create_service_container()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(get_app_version())

    app.aboutToQuit.connect(instance_guard.release)

    splash = show_splash_screen()
    startup_state = {"window": None, "error": None}

    def create_main_window() -> None:
        try:
            from ui.main_window import MainWindow

            window = MainWindow(service_container=services)
            startup_state["window"] = window
            window.setWindowTitle(APP_DISPLAY_NAME)

            if splash is not None:
                splash.finish(window)
            else:
                window.show()
        except Exception as exc:
            startup_state["error"] = exc
            services.error_service.log_exception(exc, "Main window startup failed")
            if splash is not None:
                splash.close()
            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "MUG could not start",
                    _startup_failure_message(services.error_service),
                )
            app.exit(1)

    QTimer.singleShot(STARTUP_MAIN_WINDOW_DELAY_MS, create_main_window)

    exit_code = app.exec()
    if startup_state["error"] is not None:
        raise startup_state["error"]
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
