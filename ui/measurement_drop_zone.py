from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QKeyEvent, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from domain.measurement_validation import MeasurementValidationResult


_DETAIL_LABELS = {
    "Equipment detected": "Equipamento identificado",
    "Filename": "Arquivo",
    "Measurement period": "Período da medição",
    "Integration interval": "Integralização",
    "Number of records": "Registros",
    "Status": "Status",
}


class MeasurementDropZone(QFrame):
    open_file_requested = Signal()
    file_dropped = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "idle"
        self._hovered = False
        self._drag_active = False
        self._drag_supported = True
        self._activity = 0.0
        self._hover_progress = 0.0
        self._last_result: MeasurementValidationResult | None = None

        self.setObjectName("measurementDropZone")
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(390)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("Área de seleção da medição")
        self.setAccessibleDescription(
            "Clique, pressione Enter, pressione Espaço ou arraste um arquivo de medição Primata ou Embrasul."
        )

        self._activity_timer = QTimer(self)
        self._activity_timer.setInterval(24)
        self._activity_timer.timeout.connect(self._advance_activity)

        self._hover_animation = QVariantAnimation(self)
        self._hover_animation.setDuration(170)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_animation.valueChanged.connect(self._set_hover_progress)

        self._build_ui()
        self.show_idle()

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            QFrame#measurementDropZone {
                background-color: transparent;
                border: none;
            }
            QLabel {
                background-color: transparent;
                border: none;
                color: #e8eef7;
                font-family: Arial;
            }
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)

        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(26, 28, 26, 24)
        self._layout.setSpacing(14)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_icon = QLabel("")
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon.setStyleSheet("font-size: 38px; color: #64d98a;")

        self.primary_label = QLabel()
        self.primary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.primary_label.setWordWrap(True)
        self.primary_label.setStyleSheet("""
            font-size: 23px;
            font-weight: 700;
            color: #ffffff;
        """)

        self.secondary_label = QLabel()
        self.secondary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.secondary_label.setWordWrap(True)
        self.secondary_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #aebed0;
        """)

        self.details_widget = QWidget()
        self.details_widget.setStyleSheet("background-color: transparent;")
        details_layout = QVBoxLayout()
        details_layout.setContentsMargins(0, 10, 0, 0)
        details_layout.setSpacing(12)
        self._detail_rows: dict[str, tuple[QLabel, QLabel]] = {}
        for label_text in (
            "Equipment detected",
            "Filename",
            "Measurement period",
            "Integration interval",
            "Number of records",
            "Status",
        ):
            item = QWidget()
            item.setStyleSheet("background-color: transparent; border: none;")
            item_layout = QVBoxLayout()
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(2)

            label = QLabel(_DETAIL_LABELS[label_text])
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("""
                font-size: 11px;
                color: rgba(225, 242, 231, 150);
                font-weight: 700;
                border: none;
                background-color: transparent;
            """)

            value = QLabel("")
            value.setWordWrap(True)
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value.setStyleSheet("""
                font-size: 13px;
                color: #f1fff6;
                border: none;
                background-color: transparent;
            """)

            item_layout.addWidget(label)
            item_layout.addWidget(value)
            item.setLayout(item_layout)
            details_layout.addWidget(item)
            self._detail_rows[label_text] = (label, value)

        self.details_widget.setLayout(details_layout)

        self.replace_button = QPushButton("Trocar medição")
        self.replace_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.replace_button.clicked.connect(self.open_file_requested.emit)
        self.replace_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 18);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 34);
                border-radius: 8px;
                padding: 9px 16px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 30);
                border: 1px solid rgba(255, 255, 255, 62);
            }
        """)

        self._layout.addStretch(1)
        self._layout.addWidget(self.status_icon)
        self._layout.addWidget(self.primary_label)
        self._layout.addWidget(self.secondary_label)
        self._layout.addWidget(self.details_widget)
        self._layout.addWidget(self.replace_button, 0, Qt.AlignmentFlag.AlignCenter)
        self._layout.addStretch(1)

        self.setLayout(self._layout)

    def show_idle(self) -> None:
        self._state = "idle"
        self._last_result = None
        self.status_icon.setText("↑")
        self.status_icon.setStyleSheet("font-size: 46px; color: #dceaff;")
        self.primary_label.setText("Clique para selecionar\nou arraste e solte\no arquivo aqui")
        self.primary_label.setStyleSheet("""
            font-size: 23px;
            font-weight: 700;
            color: #ffffff;
        """)
        self.secondary_label.setText(".TXT  •  .XLSX")
        self.secondary_label.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: rgba(190, 205, 222, 180);
        """)
        self.details_widget.setVisible(False)
        self.replace_button.setVisible(False)
        self._stop_activity()
        self.update()

    def set_validation_progress(self, message: str) -> None:
        self._state = "validating"
        self._last_result = None
        self.status_icon.setText("↑")
        self.status_icon.setStyleSheet("font-size: 40px; color: #dceaff;")
        self.primary_label.setText(message)
        self.secondary_label.setText("Verificando cabeçalho e compatibilidade do arquivo.")
        self.details_widget.setVisible(False)
        self.replace_button.setVisible(False)
        self._start_activity()
        self.update()

    def set_validation_result(self, result: MeasurementValidationResult) -> None:
        self._last_result = result
        self._state = "valid" if result.is_valid else "invalid"
        self.status_icon.setText("✓" if result.is_valid else "!")
        self.status_icon.setStyleSheet(
            "font-size: 42px; color: #64d98a;"
            if result.is_valid
            else "font-size: 42px; color: #ffb3aa;"
        )
        self.primary_label.setText(
            "Medição carregada com sucesso"
            if result.is_valid
            else "Arquivo inválido"
        )
        self.primary_label.setStyleSheet("""
            font-size: 21px;
            font-weight: 800;
            color: #ffffff;
        """)
        self.secondary_label.setText(
            f"{result.manufacturer}\n{result.filename}"
            if result.is_valid
            else (result.message or "Arquivo incompatível.")
        )
        self.secondary_label.setStyleSheet(
            """
            font-size: 13px;
            font-weight: 600;
            color: rgba(231, 255, 239, 205);
            """
            if result.is_valid
            else """
            font-size: 13px;
            font-weight: 600;
            color: rgba(255, 230, 225, 210);
            """
        )
        self.details_widget.setVisible(result.is_valid)
        self.replace_button.setVisible(True)
        self.replace_button.setText("Trocar medição" if result.is_valid else "Selecionar outra medição")
        self._set_detail("Equipment detected", result.manufacturer)
        self._set_detail("Filename", result.filename)
        self._set_detail("Measurement period", self._format_period(result.period))
        self._set_detail("Integration interval", result.integration_interval)
        self._set_detail("Number of records", result.records_text)
        self._set_detail("Status", result.status_label)
        self._stop_activity()
        self.update()

    def _set_detail(self, label: str, value: str) -> None:
        self._detail_rows[label][1].setText(value)

    def _format_period(self, period: str) -> str:
        parts = [part.strip() for part in str(period or "").split(" - ", 1)]
        return "\n".join(parts) if len(parts) == 2 else str(period or "")

    def _start_activity(self) -> None:
        if not self._activity_timer.isActive():
            self._activity_timer.start()

    def _stop_activity(self) -> None:
        self._activity_timer.stop()
        self._activity = 0.0

    def _advance_activity(self) -> None:
        self._activity = (self._activity + 0.018) % 1.0
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._animate_hover(1.0)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._animate_hover(0.0)
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event) -> None:
        self._animate_hover(1.0)
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        if not self._hovered:
            self._animate_hover(0.0)
        self.update()
        super().focusOutEvent(event)

    def mousePressEvent(self, event) -> None:
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.open_file_requested.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.open_file_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event) -> None:
        if self._has_local_file(event.mimeData()):
            self._drag_active = True
            self._drag_supported = self._mime_has_supported_file(event.mimeData())
            self._show_drag_feedback()
            event.acceptProposedAction()
            self.update()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._has_local_file(event.mimeData()):
            self._drag_supported = self._mime_has_supported_file(event.mimeData())
            self._show_drag_feedback()
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._drag_active = False
        self._restore_state_display()
        self.update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self._drag_active = False
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.file_dropped.emit(Path(url.toLocalFile()))
                event.acceptProposedAction()
                self.update()
                return
        event.ignore()
        self.update()

    def _has_local_file(self, mime_data) -> bool:
        return any(url.isLocalFile() for url in mime_data.urls())

    def _mime_has_supported_file(self, mime_data) -> bool:
        for url in mime_data.urls():
            if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in {".txt", ".xlsx"}:
                return True
        return False

    def _show_drag_feedback(self) -> None:
        self.status_icon.setText("↑" if self._drag_supported else "!")
        self.status_icon.setStyleSheet(
            "font-size: 44px; color: #dceaff;"
            if self._drag_supported
            else "font-size: 42px; color: #ffb3aa;"
        )
        self.details_widget.setVisible(False)
        self.replace_button.setVisible(False)
        if self._drag_supported:
            self.primary_label.setText("Solte para carregar a medição")
            self.secondary_label.setText("")
        else:
            self.primary_label.setText("Formato não suportado")
            self.secondary_label.setText("Use arquivos .txt ou .xlsx.")

    def _restore_state_display(self) -> None:
        if self._state == "validating":
            self.primary_label.setText("Validando medição...")
            self.secondary_label.setText("Verificando cabeçalho e compatibilidade do arquivo.")
            self.replace_button.setVisible(False)
            return

        if self._last_result is not None:
            self.set_validation_result(self._last_result)
            return

        self.show_idle()

    def _animate_hover(self, target: float) -> None:
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(target)
        self._hover_animation.start()

    def _set_hover_progress(self, value: object) -> None:
        self._hover_progress = float(value)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        scale_margin = 2.0 - (1.2 * self._hover_progress)
        rect = QRectF(self.rect()).adjusted(scale_margin, scale_margin, -scale_margin, -scale_margin)
        path = QPainterPath()
        path.addRoundedRect(rect, 16.0, 16.0)

        background = QLinearGradient(rect.topLeft(), rect.bottomRight())
        for position, color in self._background_stops():
            background.setColorAt(position, color)
        painter.fillPath(path, background)

        accent_strength = 0.34 + (0.24 * self._hover_progress)
        if self._hovered or self.hasFocus():
            accent_strength = max(accent_strength, 0.58)
        if self._drag_active:
            accent_strength = 0.92
        if self._drag_active and not self._drag_supported:
            accent_color = QColor(255, 92, 92)
        elif self._drag_active:
            accent_color = QColor(76, 152, 255)
        elif self._state == "valid":
            accent_color = QColor(72, 202, 120)
        elif self._state == "invalid":
            accent_color = QColor(255, 92, 92)
        else:
            accent_color = QColor(77, 141, 255)
        accent_color.setAlphaF(accent_strength)

        pen = QPen(accent_color, 1.6 if self._drag_active else 1.1)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 16.0, 16.0)

        if self._state == "validating":
            self._draw_activity_line(painter, rect, accent_color)

        event.accept()

    def _background_stops(self) -> tuple[tuple[float, QColor], ...]:
        if self._drag_active and not self._drag_supported:
            return (
                (0.0, QColor("#4a151b")),
                (0.52, QColor("#351016")),
                (1.0, QColor("#1a080b")),
            )

        if self._drag_active:
            return (
                (0.0, QColor("#173f76")),
                (0.52, QColor("#0f2f5e")),
                (1.0, QColor("#082447")),
            )

        if self._state == "valid":
            return (
                (0.0, QColor("#12351f")),
                (0.52, QColor("#0d2618")),
                (1.0, QColor("#07160f")),
            )

        if self._state == "invalid":
            return (
                (0.0, QColor("#3e1517")),
                (0.52, QColor("#2a1012")),
                (1.0, QColor("#140708")),
            )

        if self._hover_progress > 0.01 or self._hovered or self.hasFocus():
            intensity = self._hover_progress
            top = self._blend_color(QColor("#101722"), QColor("#174878"), intensity)
            middle = self._blend_color(QColor("#0b1119"), QColor("#123561"), intensity)
            bottom = self._blend_color(QColor("#06100d"), QColor("#0b2440"), intensity)
            return (
                (0.0, top),
                (0.52, middle),
                (1.0, bottom),
            )

        return (
            (0.0, QColor("#101722")),
            (0.52, QColor("#0b1119")),
            (1.0, QColor("#06100d")),
        )

    def _blend_color(self, start: QColor, end: QColor, progress: float) -> QColor:
        progress = max(0.0, min(1.0, progress))
        return QColor(
            round(start.red() + (end.red() - start.red()) * progress),
            round(start.green() + (end.green() - start.green()) * progress),
            round(start.blue() + (end.blue() - start.blue()) * progress),
        )

    def _draw_activity_line(self, painter: QPainter, rect: QRectF, accent_color: QColor) -> None:
        track = QRectF(rect.left() + 24, rect.bottom() - 18, rect.width() - 48, 2.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(36, 48, 62, 180))
        painter.drawRoundedRect(track, 1.0, 1.0)

        segment_width = max(70.0, track.width() * 0.22)
        eased = QEasingCurve(QEasingCurve.Type.InOutCubic).valueForProgress(self._activity)
        left = track.left() + (track.width() + segment_width) * eased - segment_width
        segment = QRectF(left, track.top(), segment_width, track.height())

        glow = QLinearGradient(segment.topLeft(), segment.topRight())
        transparent = QColor(accent_color)
        transparent.setAlpha(0)
        bright = QColor(accent_color)
        bright.setAlpha(230)
        glow.setColorAt(0.0, transparent)
        glow.setColorAt(0.5, bright)
        glow.setColorAt(1.0, transparent)
        painter.setBrush(glow)
        painter.drawRoundedRect(segment, 1.0, 1.0)
