import os
import subprocess
import sys
import uuid
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


ROOT = Path(__file__).resolve().parents[1]


def test_splash_module_avoids_heavy_runtime_dependencies():
    source = (ROOT / "ui" / "splash_screen.py").read_text(encoding="utf-8")

    assert "plotly" not in source
    assert "kaleido" not in source
    assert "QtWebEngine" not in source
    assert "requests" not in source
    assert "core.update_checker" not in source


def test_importing_app_does_not_load_main_window_or_update_checker():
    script = (
        "import app, sys; "
        "forbidden = ['ui.main_window', 'core.update_checker', 'plotly', 'kaleido']; "
        "loaded = [name for name in forbidden if name in sys.modules]; "
        "print(','.join(loaded)); "
        "raise SystemExit(1 if loaded else 0)"
    )
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_splash_widget_can_show_and_finish_without_chromium_or_internet():
    from PySide6.QtWidgets import QApplication
    from ui.splash_screen import MugSplashScreen

    app = QApplication.instance() or QApplication([])
    splash = MugSplashScreen()

    splash.show_splash()
    app.processEvents()

    assert splash.isVisible()

    splash.finish()
    for _ in range(30):
        app.processEvents()

    splash.close()


def test_splash_size_and_minimum_visibility_are_large_enough():
    from ui.splash_screen import (
        FADE_OUT_MS,
        FINISH_SWEEP_MS,
        MAX_SCREEN_HEIGHT_RATIO,
        MAX_SCREEN_WIDTH_RATIO,
        MINIMUM_VISIBLE_MS,
        SPLASH_HEIGHT,
        SPLASH_WIDTH,
    )

    assert 900 <= SPLASH_WIDTH <= 1000
    assert 500 <= SPLASH_HEIGHT <= 560
    assert MAX_SCREEN_WIDTH_RATIO <= 0.70
    assert MAX_SCREEN_HEIGHT_RATIO <= 0.60
    assert 1200 <= MINIMUM_VISIBLE_MS <= 1600
    assert MINIMUM_VISIBLE_MS + FINISH_SWEEP_MS + FADE_OUT_MS <= 1700


def test_splash_first_frame_is_not_translucent_or_empty():
    source = (ROOT / "ui" / "splash_screen.py").read_text(encoding="utf-8")

    assert "WA_TranslucentBackground, True" not in source
    assert "WA_OpaquePaintEvent" in source
    assert "painter.fillRect(rect, background)" in source
    assert '"MUG"' in source
    assert '"Analisador Gráfico de Grandezas Elétricas"' in source
    assert '"Inicializando..."' in source


def test_splash_uses_product_style_horizontal_composition():
    source = (ROOT / "ui" / "splash_screen.py").read_text(encoding="utf-8")

    assert "def _draw_signal_artwork" in source
    assert "def _draw_status_strip" in source
    assert "def _draw_logo" in source
    assert 'QPixmap(str(get_logo_asset_path("logo.png")))' in source
    assert "content_rect.width() * 0.38" in source
    assert "drawRoundedRect(track_rect" in source
    assert "drawEllipse(QPointF(0, 0), 178, 84)" not in source
    assert '"ECOCEL"' not in source


def test_splash_cycles_messages_and_finishes_with_activity_sweep():
    source = (ROOT / "ui" / "splash_screen.py").read_text(encoding="utf-8")

    for message in (
        "Inicializando...",
        "Carregando módulos...",
        "Inicializando interface...",
        "Preparando gráficos...",
        "Finalizando...",
    ):
        assert message in source

    assert "self._settling = True" in source
    assert "self._activity_sweep = min(1.0, settling_elapsed / FINISH_SWEEP_MS)" in source
    assert "speed *= 0.46" in source


def test_startup_stages_main_window_after_splash():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "QTimer.singleShot" in source
    assert source.find("show_splash_screen()") < source.find("from ui.main_window import MainWindow")
    assert source.find("splash.finish(window)") < source.find("window.show()")


def test_splash_finish_shows_main_window_after_fade_complete():
    source = (ROOT / "ui" / "splash_screen.py").read_text(encoding="utf-8")

    assert "self._fade_out.finished.connect(self._complete_close)" in source
    assert "self._main_window_to_activate.show()" in source


def test_single_instance_guard_prevents_second_lock():
    from app import SingleInstanceGuard

    key = f"MUG_TEST_SINGLE_INSTANCE_{uuid.uuid4()}"
    first = SingleInstanceGuard(key)
    second = SingleInstanceGuard(key)

    try:
        assert first.acquire()
        assert not second.acquire()
    finally:
        first.release()
        second.release()
