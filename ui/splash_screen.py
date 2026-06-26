from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve,
    QElapsedTimer,
    QPropertyAnimation,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QWidget

from config.paths import get_logo_asset_path


SPLASH_WIDTH = 960
SPLASH_HEIGHT = 540
MAX_SCREEN_WIDTH_RATIO = 0.70
MAX_SCREEN_HEIGHT_RATIO = 0.60
FRAME_INTERVAL_MS = 16
MINIMUM_VISIBLE_MS = 1250
FINISH_SWEEP_MS = 140
FADE_IN_MS = 420
FADE_OUT_MS = 260
LOGO_HEIGHT = 36
STARTUP_MESSAGES = (
    "Inicializando...",
    "Carregando módulos...",
    "Inicializando interface...",
    "Preparando gráficos...",
    "Finalizando...",
)


class MugSplashScreen(QWidget):
    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.SplashScreen
            | Qt.WindowType.WindowStaysOnTopHint,
        )

        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setFixedSize(self._screen_aware_size())

        self._phase = 0.0
        self._pulse = 0.0
        self._activity_sweep = 0.0
        self._settling = False
        self._closing = False
        self._started_at = QElapsedTimer()
        self._finish_started_at = QElapsedTimer()
        self._main_window_to_activate: QWidget | None = None
        self._logo = QPixmap(str(get_logo_asset_path("logo.png")))

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_in.setDuration(FADE_IN_MS)
        self._fade_in.setStartValue(0.96)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_out = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_out.setDuration(FADE_OUT_MS)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._fade_out.finished.connect(self._complete_close)

        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_INTERVAL_MS)
        self._timer.timeout.connect(self._advance_frame)

        self._center_on_screen()

    def show_splash(self) -> None:
        self._started_at.start()
        self._center_on_screen()
        self.show()
        self.raise_()
        self.update()
        self.repaint()
        self._timer.start()
        self._fade_in.start()

    def finish(self, main_window: QWidget | None = None) -> None:
        if self._closing or self._settling:
            return
        self._main_window_to_activate = main_window

        elapsed = self._started_at.elapsed() if self._started_at.isValid() else 0
        remaining_ms = max(0, MINIMUM_VISIBLE_MS - elapsed)
        if remaining_ms > 0:
            QTimer.singleShot(remaining_ms, lambda: self.finish(main_window))
            return

        self._settling = True
        self._activity_sweep = 0.0
        self._finish_started_at.start()
        QTimer.singleShot(FINISH_SWEEP_MS, self._start_fade_out)

    def _start_fade_out(self) -> None:
        if self._closing:
            return
        self._activity_sweep = 1.0
        self._settling = False
        self._closing = True
        self._fade_in.stop()
        self._fade_out.start()

    def _complete_close(self) -> None:
        self._timer.stop()
        if self._main_window_to_activate is not None:
            self._main_window_to_activate.show()
            self._main_window_to_activate.raise_()
            self._main_window_to_activate.activateWindow()
        self.close()

    def _screen_aware_size(self) -> QSize:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return QSize(SPLASH_WIDTH, SPLASH_HEIGHT)

        available = screen.availableGeometry()
        max_width = int(available.width() * MAX_SCREEN_WIDTH_RATIO)
        max_height = int(available.height() * MAX_SCREEN_HEIGHT_RATIO)
        scale = min(1.0, max_width / SPLASH_WIDTH, max_height / SPLASH_HEIGHT)

        return QSize(
            max(420, int(SPLASH_WIDTH * scale)),
            max(260, int(SPLASH_HEIGHT * scale)),
        )

    def _center_on_screen(self) -> None:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.move(
            available.center().x() - self.width() // 2,
            available.center().y() - self.height() // 2,
        )

    def _advance_frame(self) -> None:
        speed = 0.095
        if self._settling:
            settling_elapsed = self._finish_started_at.elapsed()
            self._activity_sweep = min(1.0, settling_elapsed / FINISH_SWEEP_MS)
            speed *= 0.46
        elif self._closing:
            speed *= 0.32
        else:
            self._activity_sweep = (self._activity_sweep + 0.018) % 1.0

        self._phase = (self._phase + speed) % (math.tau * 1000)
        self._pulse = (self._pulse + 0.045) % math.tau
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = QRectF(0, 0, self.width(), self.height())
        self._draw_background(painter, rect)

        panel_rect = rect.adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor(255, 255, 255, 24), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(panel_rect)

        content_rect = rect.adjusted(58, 42, -58, -44)
        self._draw_signal_artwork(painter, content_rect)
        self._draw_identity(painter, content_rect)
        self._draw_status_strip(painter, content_rect)

    def _draw_background(self, painter: QPainter, rect: QRectF) -> None:
        background = QLinearGradient(rect.topLeft(), rect.bottomRight())
        background.setColorAt(0.0, QColor(18, 20, 23))
        background.setColorAt(0.40, QColor(8, 13, 17))
        background.setColorAt(0.76, QColor(7, 25, 31))
        background.setColorAt(1.0, QColor(3, 6, 8))
        painter.fillRect(rect, background)

        radial = QRadialGradient(
            QPointF(rect.right() - rect.width() * 0.18, rect.top() + rect.height() * 0.18),
            rect.width() * 0.62,
        )
        radial.setColorAt(0.0, QColor(78, 130, 142, 62))
        radial.setColorAt(0.38, QColor(25, 84, 98, 32))
        radial.setColorAt(0.68, QColor(24, 130, 91, 18))
        radial.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, radial)

        painter.save()
        painter.setPen(QPen(QColor(255, 255, 255, 6), 1))
        spacing = max(30, int(self.width() * 0.052))
        for offset in range(-self.height(), self.width(), spacing):
            painter.drawLine(
                QPointF(offset, self.height()),
                QPointF(offset + self.height() * 0.72, 0),
            )
        painter.setPen(QPen(QColor(98, 136, 136, 5), 1))
        for x in range(0, self.width(), spacing):
            painter.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        painter.restore()

    def _draw_signal_artwork(self, painter: QPainter, content_rect: QRectF) -> None:
        artwork_rect = QRectF(
            content_rect.left() + content_rect.width() * 0.38,
            content_rect.top() + content_rect.height() * 0.08,
            content_rect.width() * 0.62,
            content_rect.height() * 0.66,
        )

        painter.save()
        painter.setClipRect(artwork_rect.adjusted(-24, -24, 24, 24))

        center_y = artwork_rect.center().y()
        colors = (
            QColor(58, 190, 135, 166),
            QColor(68, 150, 194, 126),
            QColor(210, 228, 226, 60),
        )

        for index, color in enumerate(colors):
            base_y = center_y + (index - 1) * artwork_rect.height() * 0.14
            amplitude = artwork_rect.height() * (
                0.045 + index * 0.015 + 0.009 * math.sin(self._pulse + index * 1.7)
            )
            frequency = 2.35 + index * 0.58
            phase = self._phase * (0.70 + index * 0.21) + index * 1.35
            path = QPainterPath()
            path.moveTo(artwork_rect.left(), base_y)

            steps = 132
            points: list[QPointF] = []
            for step in range(steps + 1):
                ratio = step / steps
                point = self._signal_point(
                    artwork_rect,
                    base_y,
                    amplitude,
                    frequency,
                    phase,
                    ratio,
                )
                points.append(point)
                path.lineTo(point)

            glow_pen = QPen(QColor(color.red(), color.green(), color.blue(), max(28, color.alpha() // 4)), 6.5)
            glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

            pen = QPen(color, 1.7 + index * 0.34)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPath(path)

            pulse_ratio = (self._activity_sweep + index * 0.21) % 1.0
            pulse_point = self._signal_point(
                artwork_rect,
                base_y,
                amplitude,
                frequency,
                phase,
                pulse_ratio,
            )
            pulse_alpha = 150 + int(55 * math.sin(self._pulse + index))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), max(55, pulse_alpha // 3)))
            painter.drawEllipse(pulse_point, 10.5, 10.5)
            painter.setBrush(QColor(222, 255, 241, pulse_alpha))
            painter.drawEllipse(pulse_point, 3.2, 3.2)

        painter.restore()

    def _signal_point(
        self,
        artwork_rect: QRectF,
        base_y: float,
        amplitude: float,
        frequency: float,
        phase: float,
        ratio: float,
    ) -> QPointF:
        x = artwork_rect.left() + artwork_rect.width() * ratio
        envelope = 0.22 + 0.78 * math.sin(math.pi * ratio)
        carrier = math.sin(phase + ratio * math.tau * frequency)
        harmonic = math.sin(phase * 0.62 + ratio * math.tau * 7.2) * 0.16
        y = base_y + (carrier + harmonic) * amplitude * envelope
        return QPointF(x, y)

    def _draw_identity(self, painter: QPainter, content_rect: QRectF) -> None:
        elapsed = self._started_at.elapsed() if self._started_at.isValid() else 0
        intro = min(1.0, elapsed / FADE_IN_MS)

        painter.save()
        painter.setOpacity(0.88 + 0.12 * intro)
        painter.translate(0, 7 * (1.0 - intro))

        self._draw_logo(painter, content_rect)

        painter.setPen(QPen(QColor(86, 196, 151), 2.3))
        painter.drawLine(
            QPointF(content_rect.left(), content_rect.top() + 72),
            QPointF(content_rect.left() + 88, content_rect.top() + 72),
        )

        title_font = QFont("Segoe UI", max(52, int(self.height() * 0.132)), QFont.Weight.Bold)
        title_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 102)
        title_rect = QRectF(content_rect.left(), content_rect.top() + 105, 330, 88)
        scale = 0.98 + 0.02 * intro

        painter.save()
        painter.translate(title_rect.left(), title_rect.center().y())
        painter.scale(scale, scale)
        painter.translate(-title_rect.left(), -title_rect.center().y())
        painter.setFont(title_font)
        shadow_rect = title_rect.translated(0, 2.5)
        painter.setPen(QColor(0, 0, 0, 96))
        painter.drawText(shadow_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "MUG")
        painter.setPen(QColor(77, 183, 145, 42))
        painter.drawText(title_rect.translated(2.2, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "MUG")
        painter.setPen(QColor(247, 250, 249))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "MUG")
        painter.restore()

        painter.setPen(QColor(210, 219, 218, 214))
        subtitle_font = QFont("Segoe UI", max(12, int(self.height() * 0.030)), QFont.Weight.Normal)
        painter.setFont(subtitle_font)
        painter.drawText(
            QRectF(content_rect.left(), content_rect.top() + 194, 405, 60),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            "Analisador Gráfico de Grandezas Elétricas",
        )

        version_text = QApplication.applicationVersion()
        if version_text:
            painter.setPen(QColor(130, 145, 146, 156))
            version_font = QFont("Segoe UI", max(9, int(self.height() * 0.021)))
            painter.setFont(version_font)
            painter.drawText(
                QRectF(content_rect.left(), content_rect.bottom() - 88, 220, 24),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                version_text,
            )
        painter.restore()

    def _draw_logo(self, painter: QPainter, content_rect: QRectF) -> None:
        if self._logo.isNull():
            return

        logo_height = max(32, min(40, int(self.height() * 0.067)))
        logo_width = int(self._logo.width() * logo_height / self._logo.height())
        logo = self._logo.scaled(
            logo_width,
            logo_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(
            int(content_rect.left()),
            int(content_rect.top() + 4),
            logo,
        )

    def _draw_status_strip(self, painter: QPainter, content_rect: QRectF) -> None:
        strip = QRectF(
            content_rect.left(),
            content_rect.bottom() - 44,
            content_rect.width(),
            44,
        )
        progress_y = strip.bottom() - 8

        painter.save()
        painter.setPen(QPen(QColor(255, 255, 255, 16), 1))
        painter.drawLine(QPointF(strip.left(), strip.top()), QPointF(strip.right(), strip.top()))

        painter.setPen(QColor(190, 202, 203, 190))
        status_font = QFont("Segoe UI", max(10, int(self.height() * 0.024)), QFont.Weight.Normal)
        painter.setFont(status_font)
        painter.drawText(
            QRectF(strip.left(), strip.top() + 8, 260, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._startup_message(),
        )

        painter.setPen(QColor(112, 126, 128, 144))
        detail_font = QFont("Segoe UI", max(8, int(self.height() * 0.019)), QFont.Weight.Normal)
        painter.setFont(detail_font)
        painter.drawText(
            QRectF(strip.right() - 260, strip.top() + 8, 260, 24),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "Atividade de inicialização",
        )

        track_rect = QRectF(strip.left(), progress_y, strip.width(), 1.8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 20))
        painter.drawRoundedRect(track_rect, 0.9, 0.9)

        sweep_width = track_rect.width() * 0.20
        sweep_start = track_rect.left() + self._activity_sweep * (track_rect.width() - sweep_width)
        sweep = QLinearGradient(
            QPointF(sweep_start, progress_y),
            QPointF(sweep_start + sweep_width, progress_y),
        )
        sweep.setColorAt(0.0, QColor(50, 180, 130, 0))
        sweep.setColorAt(0.50, QColor(72, 214, 168, 205))
        sweep.setColorAt(1.0, QColor(74, 154, 205, 0))
        painter.setBrush(sweep)
        painter.drawRoundedRect(QRectF(sweep_start, progress_y, sweep_width, 1.8), 0.9, 0.9)
        painter.restore()

    def _startup_message(self) -> str:
        if self._settling or self._closing:
            return STARTUP_MESSAGES[-1]
        elapsed = self._started_at.elapsed() if self._started_at.isValid() else 0
        index = min(len(STARTUP_MESSAGES) - 2, elapsed // 260)
        return STARTUP_MESSAGES[int(index)]

def show_splash_screen() -> MugSplashScreen | None:
    try:
        splash = MugSplashScreen()
        splash.show_splash()
        QApplication.processEvents()
        return splash
    except Exception as exc:
        print(f"[SPLASH ERROR] {exc}")
        return None
