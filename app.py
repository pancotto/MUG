import sys

from PySide6.QtCore import QSharedMemory, QTimer
from PySide6.QtWidgets import QApplication

from ui.splash_screen import show_splash_screen


SINGLE_INSTANCE_KEY = "MUG_DESKTOP_SINGLE_INSTANCE"


class SingleInstanceGuard:
    def __init__(self, key: str):
        self._memory = QSharedMemory(key)
        self._owns_lock = False

    def acquire(self) -> bool:
        try:
            self._owns_lock = self._memory.create(1)
            return self._owns_lock
        except Exception as exc:
            print(f"[STARTUP GUARD ERROR] {exc}")
            return True

    def release(self) -> None:
        try:
            if self._owns_lock and self._memory.isAttached():
                self._memory.detach()
        except Exception as exc:
            print(f"[STARTUP GUARD ERROR] {exc}")


def _read_version_for_app() -> str:
    try:
        from pathlib import Path

        version = (Path(__file__).resolve().parent / "VERSION").read_text(
            encoding="utf-8"
        ).strip()
        if version:
            return version
    except Exception:
        pass
    return ""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MUG")
    app.setApplicationVersion(_read_version_for_app())

    instance_guard = SingleInstanceGuard(SINGLE_INSTANCE_KEY)
    if not instance_guard.acquire():
        return 0

    app.aboutToQuit.connect(instance_guard.release)

    splash = show_splash_screen()
    startup_state = {"window": None, "error": None}

    def create_main_window() -> None:
        try:
            from ui.main_window import MainWindow

            window = MainWindow()
            startup_state["window"] = window

            if splash is not None:
                splash.finish(window)
            else:
                window.show()
        except Exception as exc:
            startup_state["error"] = exc
            if splash is not None:
                splash.close()
            app.exit(1)

    QTimer.singleShot(250, create_main_window)

    exit_code = app.exec()
    if startup_state["error"] is not None:
        raise startup_state["error"]
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
