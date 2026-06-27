from pathlib import Path

from config.paths import get_asset_path, get_logo_asset_path
from config.versions import format_app_version as _format_app_version
from config.versions import get_app_version as _get_app_version
from domain.input_rules import (
    AnalysisInputValues,
    build_input_data,
    normalize_analysis_values,
    validate_analysis_values,
)
from domain.measurement_validation import MeasurementValidationResult
from services.container import get_service_container


APP_VERSION_FALLBACK = "1.6.1"


def get_app_version() -> str:
    """
    Retorna a versão da aplicação no padrão SemVer.

    Em desenvolvimento, lê o arquivo VERSION na raiz do projeto.
    Em build PyInstaller --onedir, tenta ler VERSION ao lado do executável
    ou dentro da pasta _internal, quando incluído via --add-data.
    """
    return _get_app_version(APP_VERSION_FALLBACK)


def format_app_version(version: str) -> str:
    return _format_app_version(version)


from PySide6.QtCore import Qt, QObject, Signal, Slot, QThread, QTimer
from PySide6.QtGui import QColor, QPixmap
from ui.about_dialog import AboutDialog
from ui.input_validation import (
    enable_uppercase_input,
    set_decimal_number_validator,
    set_digits_only_validator,
)
from ui.measurement_drop_zone import MeasurementDropZone

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QFrame,
    QDialog,
    QHBoxLayout,
    QProgressBar,
    QButtonGroup,
    QScrollArea,
    QSizePolicy,
    QBoxLayout,
    QGraphicsDropShadowEffect,
)


class ClickableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._callback = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_click_callback(self, callback):
        self._callback = callback

    def mousePressEvent(self, event):
        if self._callback:
            self._callback()
        super().mousePressEvent(event)


class ReferenceImageCard(QFrame):
    def __init__(
        self,
        title: str,
        image_path: Path,
        callback,
        logo_path: Path | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._callback = callback
        self._image_pixmap = QPixmap(str(image_path))
        self._logo_pixmap = QPixmap(str(logo_path)) if logo_path else QPixmap()
        self._hovered = False

        self.setObjectName("referenceImageCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(230, 190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName(f"Referência {title}")
        self.setAccessibleDescription(f"Abrir imagem de referência {title}.")
        self.setToolTip("Clique para ampliar a referência")
        self.setStyleSheet("""
            QFrame#referenceImageCard {
                background-color: #101725;
                border: 1px solid #1d2b40;
                border-radius: 12px;
            }
            QFrame#referenceImageCard:hover {
                background-color: #13233a;
                border: 1px solid #2f7df0;
            }
            QLabel {
                background-color: transparent;
                border: none;
            }
        """)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setOffset(0, 0)
        self._shadow.setColor(QColor(47, 125, 240, 0))
        self.setGraphicsEffect(self._shadow)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.logo_label.setVisible(not self._logo_pixmap.isNull())
        self.logo_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.title_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 700;
            color: #eaf1fb;
        """)

        header_layout.addWidget(self.logo_label, 0)
        header_layout.addWidget(self.title_label, 1)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(120)
        self.image_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border-radius: 8px;
                padding: 4px;
            }
        """)

        layout.addLayout(header_layout)
        layout.addWidget(self.image_label, 1)
        self.setLayout(layout)

        self._refresh_pixmaps()

    def resizeEvent(self, event):
        self._refresh_pixmaps()
        super().resizeEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self._shadow.setBlurRadius(26)
        self._shadow.setOffset(0, 4)
        self._shadow.setColor(QColor(47, 125, 240, 95))
        self._refresh_pixmaps()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._shadow.setBlurRadius(0)
        self._shadow.setOffset(0, 0)
        self._shadow.setColor(QColor(47, 125, 240, 0))
        self._refresh_pixmaps()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._callback()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._callback()
            event.accept()
            return
        super().keyPressEvent(event)

    def _refresh_pixmaps(self):
        if not self._logo_pixmap.isNull():
            self.logo_label.setPixmap(
                self._logo_pixmap.scaled(
                    86,
                    34,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        if self._image_pixmap.isNull():
            return

        available = self.image_label.contentsRect().size()
        if available.width() <= 0 or available.height() <= 0:
            return

        zoom = 1.025 if self._hovered else 1.0
        self.image_label.setPixmap(
            self._image_pixmap.scaled(
                max(1, int((available.width() - 8) * zoom)),
                max(1, int((available.height() - 8) * zoom)),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class MeasurementReferenceSection(QWidget):
    def __init__(self, title: QLabel, cards: list[ReferenceImageCard], parent=None):
        super().__init__(parent)
        self._cards = cards
        self._stacked = False
        self.setObjectName("measurementReferenceSection")
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("""
            QWidget#measurementReferenceSection {
                background-color: transparent;
                border: none;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        self.cards_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(14)
        for card in self._cards:
            self.cards_layout.addWidget(card, 1)

        layout.addWidget(title)
        layout.addLayout(self.cards_layout, 1)
        self.setLayout(layout)

    def resizeEvent(self, event):
        self._update_direction()
        super().resizeEvent(event)

    def showEvent(self, event):
        self._update_direction()
        super().showEvent(event)

    def _update_direction(self):
        window_width = self.window().width() if self.window() else self.width()
        should_stack = window_width < 1400
        if should_stack == self._stacked:
            return

        self._stacked = should_stack
        self.cards_layout.setDirection(
            QBoxLayout.Direction.TopToBottom
            if self._stacked
            else QBoxLayout.Direction.LeftToRight
        )
        self.setMinimumHeight(430 if self._stacked else 250)
        for card in self._cards:
            card.setMinimumHeight(175 if self._stacked else 190)


class DataProcessingWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, input_data, data_processing_service):
        super().__init__()
        self.input_data = input_data
        self.data_processing_service = data_processing_service

    @Slot()
    def run(self):
        try:
            processed = self.data_processing_service.process(self.input_data)
            self.finished.emit(processed)
        except Exception as exc:
            self.error.emit(str(exc))


class InputPage(QWidget):
    def __init__(self, main_window, service_container=None):
        super().__init__()
        self.main_window = main_window
        self.services = service_container or get_service_container()
        self.selected_excel_path: Path | None = None
        self.measurement_validation: MeasurementValidationResult | None = None
        self.assets = self.services.assets
        self._processing_thread: QThread | None = None
        self._processing_worker: DataProcessingWorker | None = None
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                color: #f1f1f1;
                font-family: Arial;
            }
        """)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(30, 25, 30, 25)
        root_layout.setSpacing(18)
        root_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("MUG - ANALISADOR GRÁFICO DE GRANDEZAS ELÉTRICAS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            color: #ffffff;
            margin-bottom: 18px;
            background-color: transparent;
            padding: 0px;
        """)

        form_card = QFrame()
        form_card.setObjectName("inputFormCard")
        form_card.setMinimumWidth(760)
        form_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        form_card.setStyleSheet("""
            QFrame#inputFormCard {
                background-color: #000000;
                border: 1px solid #000000;
                border-radius: 12px;
            }
        """)

        form_layout = QVBoxLayout()
        form_layout.setContentsMargins(26, 22, 26, 18)
        form_layout.setSpacing(12)
        form_layout.addWidget(title)

        self.company_input = self._create_labeled_input("EMPRESA", "Ex.: ECOCEL")
        self.city_input = self._create_labeled_input("CIDADE/ES", "Ex.: VITÓRIA/ES")
        self.equipment_selector = self._create_equipment_selector()
        self.equipment_reference_input = self._create_labeled_input("REFERÊNCIA / TAG", "Ex.: TRAFO 01")
        self.equipment_value_input = self._create_labeled_input("POTÊNCIA (kVA)", "Ex.: 500")
        self.local_input = self._create_labeled_input("LOCAL", "Ex.: LADO FONTE ou LADO CARGA")
        self.revision_input = self._create_labeled_input("REVISÃO", "Ex.: 00")
        self.revision_input["input"].setText("00")

        self.measurement_step_title = QLabel("ETAPA 1 - SELECIONAR MEDIÇÃO")
        self.measurement_step_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.measurement_step_title.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #ffffff;
            background-color: transparent;
        """)

        self.measurement_step_subtitle = QLabel(
            "Selecione ou arraste o arquivo da medição para iniciar a análise."
        )
        self.measurement_step_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.measurement_step_subtitle.setWordWrap(True)
        self.measurement_step_subtitle.setStyleSheet("""
            font-size: 13px;
            color: #9fb0c4;
            background-color: transparent;
        """)

        self.drop_zone = MeasurementDropZone()
        self.drop_zone.open_file_requested.connect(self.select_data_file)
        self.drop_zone.file_dropped.connect(self.handle_selected_file)

        self.metadata_step_title = QLabel("ETAPA 2 - COMPLETAR IDENTIFICAÇÃO")
        self.metadata_step_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.metadata_step_title.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #ffffff;
            background-color: transparent;
        """)

        self.generate_button = QPushButton("GERAR GRÁFICOS")
        self.generate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_button.setStyleSheet("""
            QPushButton {
                background-color: #1f5fbf;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 18px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #194f9e;
            }
            QPushButton:disabled {
                background-color: #173f7d;
                color: #d0d0d0;
            }
        """)
        self.generate_button.clicked.connect(self.on_generate_clicked)
        self.generate_button.setDisabled(True)
        self.generate_button.setToolTip("Selecione uma medição válida primeiro.")

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setVisible(False)
        self.status_label.setStyleSheet("""
            color: #bbbbbb;
            background-color: #000000;
            font-size: 13px;
            font-weight: bold;
        """)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("Processando dados e gerando gráficos... aguarde")
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #222222;
                border-radius: 8px;
                background-color: #000000;
                color: white;
                text-align: center;
                min-height: 22px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #2d6cdf;
                border-radius: 7px;
            }
        """)

        self._enable_uppercase_input(self.company_input["input"])
        self._enable_uppercase_input(self.city_input["input"])
        self._enable_uppercase_input(self.local_input["input"])
        self._enable_uppercase_input(self.equipment_reference_input["input"])
        set_digits_only_validator(self.revision_input["input"])
        set_decimal_number_validator(self.equipment_value_input["input"])

        top_row_layout = QHBoxLayout()
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(14)
        top_row_layout.addWidget(self.company_input["container"], 1)
        top_row_layout.addWidget(self.city_input["container"], 1)
        top_row_layout.addWidget(self.revision_input["container"], 0)
        self.revision_input["container"].setMaximumWidth(190)
        self.revision_input["container"].setMinimumWidth(145)

        equipment_row_layout = QHBoxLayout()
        equipment_row_layout.setContentsMargins(0, 0, 0, 0)
        equipment_row_layout.setSpacing(0)
        equipment_row_layout.addWidget(self.equipment_selector["container"])

        data_row_layout = QHBoxLayout()
        data_row_layout.setContentsMargins(0, 0, 0, 0)
        data_row_layout.setSpacing(14)
        data_row_layout.addWidget(self.local_input["container"], 1)
        data_row_layout.addWidget(self.equipment_reference_input["container"], 1)
        data_row_layout.addWidget(self.equipment_value_input["container"], 1)

        left_column = QWidget()
        left_column.setMinimumWidth(260)
        left_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_column.setStyleSheet("background-color: transparent;")
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        left_layout.addWidget(self.measurement_step_title)
        left_layout.addWidget(self.measurement_step_subtitle)
        left_layout.addWidget(self.drop_zone, 1)
        left_column.setLayout(left_layout)

        right_column = QWidget()
        right_column.setMinimumWidth(430)
        right_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_column.setStyleSheet("background-color: transparent;")
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(14)
        right_layout.addWidget(self.metadata_step_title)
        right_layout.addLayout(top_row_layout)
        right_layout.addLayout(equipment_row_layout)
        right_layout.addLayout(data_row_layout)
        right_layout.addSpacing(8)
        right_layout.addWidget(self.generate_button)
        right_layout.addWidget(self.status_label)
        right_layout.addWidget(self.progress_bar)
        reference_section = self._create_reference_section()
        if reference_section:
            right_layout.addWidget(reference_section, 1)
        else:
            right_layout.addStretch(1)
        right_column.setLayout(right_layout)

        workflow_layout = QHBoxLayout()
        workflow_layout.setContentsMargins(0, 0, 0, 0)
        workflow_layout.setSpacing(28)
        workflow_layout.addWidget(left_column, 1)
        workflow_layout.addWidget(right_column, 2)
        form_layout.addLayout(workflow_layout, 1)

        self.version_label = ClickableLabel()
        self.version_label.setText(format_app_version(get_app_version()))
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setToolTip("Sobre o MUG")
        self.version_label.setStyleSheet("""
            QLabel {
                color: #8a8a8a;
                background-color: transparent;
                font-size: 11px;
                font-weight: bold;
                padding-top: 2px;
            }
            QLabel:hover {
                color: #bdbdbd;
            }
        """)
        self.version_label.set_click_callback(self.show_about_dialog)

        form_layout.addWidget(self.version_label)

        form_card.setLayout(form_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
            QScrollBar:vertical {
                background: #111111;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #444444;
                min-height: 30px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        scroll_container = QWidget()
        scroll_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll_container.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout()
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.addWidget(form_card, 1)
        scroll_container.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_container)

        root_layout.addWidget(scroll_area, 1)
        self.setLayout(root_layout)

    def _enable_uppercase_input(self, line_edit: QLineEdit):
        enable_uppercase_input(line_edit)

    def _create_equipment_selector(self):
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel("EQUIPAMENTO")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #f1f1f1;
            background-color: transparent;
        """)

        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)

        self.trafo_radio = QPushButton()
        self.breaker_radio = QPushButton()

        self.trafo_radio.setCheckable(True)
        self.breaker_radio.setCheckable(True)
        self.trafo_radio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.breaker_radio.setCursor(Qt.CursorShape.PointingHandCursor)

        selector_style = """
            QPushButton {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton:checked {
                border: 1px solid #4d8dff;
                background-color: #203a63;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #333333;
            }
            QPushButton:checked:hover {
                background-color: #254477;
            }
        """

        self.trafo_radio.setStyleSheet(selector_style)
        self.breaker_radio.setStyleSheet(selector_style)

        self.equipment_button_group = QButtonGroup(self)
        self.equipment_button_group.addButton(self.trafo_radio)
        self.equipment_button_group.addButton(self.breaker_radio)
        self.equipment_button_group.setExclusive(True)

        self.trafo_radio.setChecked(True)
        self._update_equipment_selector_texts()

        self.trafo_radio.toggled.connect(self._on_equipment_type_changed)
        self.breaker_radio.toggled.connect(self._on_equipment_type_changed)

        options_layout.addWidget(self.trafo_radio)
        options_layout.addWidget(self.breaker_radio)

        layout.addWidget(label)
        layout.addLayout(options_layout)
        container.setLayout(layout)

        return {
            "container": container,
            "trafo_radio": self.trafo_radio,
            "breaker_radio": self.breaker_radio,
        }

    def _update_equipment_selector_texts(self):
        if not hasattr(self, "trafo_radio") or not hasattr(self, "breaker_radio"):
            return

        self.trafo_radio.setText("●  TRANSFORMADOR" if self.trafo_radio.isChecked() else "○  TRANSFORMADOR")
        self.breaker_radio.setText("●  DISJUNTOR" if self.breaker_radio.isChecked() else "○  DISJUNTOR")

    def _on_equipment_type_changed(self):
        self._update_equipment_selector_texts()

        if not hasattr(self, "equipment_value_input"):
            return

        if self.get_equipment_type() == "DISJUNTOR":
            self.equipment_value_input["label"].setText("CORRENTE (A)")
            self.equipment_value_input["input"].setPlaceholderText("Ex.: 500")
            self.equipment_reference_input["input"].setPlaceholderText("Ex.: DJ GERAL")
            self.local_input["input"].setPlaceholderText("Ex.: QGBT")
        else:
            self.equipment_value_input["label"].setText("POTÊNCIA (kVA)")
            self.equipment_value_input["input"].setPlaceholderText("Ex.: 500")
            self.equipment_reference_input["input"].setPlaceholderText("Ex.: TRAFO 01")
            self.local_input["input"].setPlaceholderText("Ex.: LADO FONTE ou LADO CARGA")

    def get_equipment_type(self) -> str:
        if getattr(self, "breaker_radio", None) and self.breaker_radio.isChecked():
            return "DISJUNTOR"
        return "TRAFO"

    def _create_labeled_input(self, label_text: str, placeholder: str):
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #f1f1f1;
            background-color: transparent;
        """)

        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        line_edit.setMinimumHeight(42)
        line_edit.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #4d8dff;
            }
        """)

        layout.addWidget(label)
        layout.addWidget(line_edit)
        container.setLayout(layout)

        return {
            "container": container,
            "label": label,
            "input": line_edit,
        }

    def _create_reference_section(self):
        title = QLabel("REFERÊNCIAS DOS MEDIDORES")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 12px;
            font-weight: 700;
            color: #9fb0c4;
            background-color: transparent;
        """)

        primata_card = self._create_reference_card(
            title="Primata P55",
            image_attr="primata_cola",
            fallback_image="primata_cola.png",
            logo_attr="primata_logo",
            fallback_logo="primata_logo.png",
            callback=self.show_primata_cola,
        )
        embrasul_card = self._create_reference_card(
            title="Embrasul RE7080",
            image_attr="embrasul_cola",
            fallback_image="embrasul_cola.png",
            logo_attr="embrasul_logo",
            fallback_logo="embrasul_logo.png",
            callback=self.show_embrasul_cola,
        )

        cards = []
        if primata_card:
            cards.append(primata_card)
        if embrasul_card:
            cards.append(embrasul_card)

        if not cards:
            return None

        return MeasurementReferenceSection(title, cards)

    def _create_reference_card(
        self,
        title: str,
        image_attr: str,
        fallback_image: str,
        logo_attr: str,
        fallback_logo: str,
        callback,
    ):
        image_path = self._resolve_asset_path(image_attr, fallback_image)
        if not image_path or not image_path.exists():
            return None

        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            return None

        logo_path = self._resolve_asset_path(logo_attr, fallback_logo, logo=True)

        return ReferenceImageCard(
            title=title,
            image_path=image_path,
            logo_path=logo_path,
            callback=callback,
        )

    def _resolve_asset_path(
        self,
        asset_attr: str,
        fallback_filename: str,
        logo: bool = False,
    ) -> Path | None:
        asset_path = None

        if self.assets and getattr(self.assets, asset_attr, None):
            asset_path = getattr(self.assets, asset_attr)

        if not asset_path:
            resolver = get_logo_asset_path if logo else get_asset_path
            asset_path = resolver(fallback_filename)

        asset_path = Path(asset_path)
        return asset_path if asset_path.exists() else None

    def show_primata_cola(self):
        self._show_cola_dialog(
            title="Colinha do Primata",
            cola_attr="primata_cola",
            fallback_filename="primata_cola.png",
        )

    def show_embrasul_cola(self):
        self._show_cola_dialog(
            title="Colinha da Embrasul",
            cola_attr="embrasul_cola",
            fallback_filename="embrasul_cola.png",
        )

    def _show_cola_dialog(self, title: str, cola_attr: str, fallback_filename: str):
        cola_path = None

        if self.assets and getattr(self.assets, cola_attr, None):
            cola_path = getattr(self.assets, cola_attr)

        if not cola_path:
            cola_path = get_asset_path(fallback_filename)

        if not cola_path or not Path(cola_path).exists():
            QMessageBox.warning(
                self,
                title,
                f"Imagem não encontrada:\n\n{fallback_filename}"
            )
            return

        pixmap = QPixmap(str(cola_path))
        if pixmap.isNull():
            QMessageBox.warning(
                self,
                title,
                "Não foi possível carregar a imagem."
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(900, 620)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                background-color: #ffffff;
                color: #202020;
                font-family: Arial;
            }
            QPushButton {
                background-color: #0d6efd;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: none;
            }
        """)
        image_label.setPixmap(
            pixmap.scaled(
                860,
                500,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        close_button = QPushButton("Fechar")
        close_button.clicked.connect(dialog.close)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)

        layout.addWidget(image_label)
        layout.addLayout(button_layout)

        dialog.setLayout(layout)
        dialog.exec()

    def show_about_dialog(self):

        dialog = AboutDialog(
            self,
            app_version=format_app_version(get_app_version()),
            update_service=self.services.update_service,
            available_update=getattr(
                self.main_window,
                "available_update",
                None
            )
        )

        dialog.exec()


    def select_data_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo de medição",
            "",
            "Arquivos de medição (*.txt *.xlsx);;Texto Primata/Embrasul (*.txt);;Planilha Primata (*.xlsx);;Todos os arquivos (*)"
        )

        if file_path:
            self.handle_selected_file(Path(file_path))

    def handle_selected_file(self, file_path: Path):
        self.selected_excel_path = Path(file_path)
        self.measurement_validation = None
        self.drop_zone.set_validation_progress("Selecionando arquivo...")
        self._update_generate_button_availability()
        QTimer.singleShot(0, lambda: self._start_measurement_validation(Path(file_path)))

    def _start_measurement_validation(self, file_path: Path):
        self.drop_zone.set_validation_progress("Validando medição...")
        QTimer.singleShot(0, lambda: self._finish_measurement_validation(file_path))

    def _finish_measurement_validation(self, file_path: Path):
        try:
            result = self.services.measurement_validation_service.validate(file_path)
        except Exception as exc:
            self.services.error_service.log_exception(
                exc,
                "Falha na validação da medição",
            )
            result = MeasurementValidationResult(
                path=file_path,
                status="invalid",
                file_type=file_path.suffix.lower().lstrip(".").upper(),
                message="Falha ao validar a medição.",
            )

        self.measurement_validation = result
        self.selected_excel_path = result.path
        self.drop_zone.set_validation_result(result)
        self._update_generate_button_availability()

    def _update_generate_button_availability(self):
        can_generate = (
            self.selected_excel_path is not None
            and self.measurement_validation is not None
            and self.measurement_validation.is_valid
        )
        self.generate_button.setDisabled(not can_generate)
        self.generate_button.setToolTip(
            ""
            if can_generate
            else "Selecione uma medição válida primeiro."
        )

    def normalize_inputs(self):
        values = normalize_analysis_values(self._analysis_input_values())
        self.company_input["input"].setText(values.company)
        self.city_input["input"].setText(values.city)
        self.equipment_reference_input["input"].setText(values.equipment_reference)
        self.local_input["input"].setText(values.local)
        self.revision_input["input"].setText(values.revision)
        self.equipment_value_input["input"].setText(values.equipment_value)

    def _analysis_input_values(self) -> AnalysisInputValues:
        return AnalysisInputValues(
            company=self.company_input["input"].text(),
            city=self.city_input["input"].text(),
            equipment_type=self.get_equipment_type(),
            equipment_reference=self.equipment_reference_input["input"].text(),
            equipment_value=self.equipment_value_input["input"].text(),
            local=self.local_input["input"].text(),
            revision=self.revision_input["input"].text(),
            selected_path=self.selected_excel_path,
            measurement_is_valid=(
                True
                if self.measurement_validation is None
                else self.measurement_validation.is_valid
            ),
        )

    def validate_form(self) -> tuple[bool, str]:
        self.normalize_inputs()
        return validate_analysis_values(self._analysis_input_values())

    def set_processing_state(self, processing: bool):
        self.generate_button.setDisabled(processing)
        self.drop_zone.setDisabled(processing)

        for field in [
            self.company_input["input"],
            self.city_input["input"],
            self.equipment_reference_input["input"],
            self.equipment_value_input["input"],
            self.local_input["input"],
            self.revision_input["input"],
        ]:
            field.setDisabled(processing)

        self.trafo_radio.setDisabled(processing)
        self.breaker_radio.setDisabled(processing)

        self.status_label.setVisible(processing)
        self.progress_bar.setVisible(processing)

        if processing:
            self.generate_button.setText("GERANDO GRÁFICOS...")
            self.status_label.setText("Processando dados e montando os gráficos. Aguarde...")
        else:
            self.generate_button.setText("GERAR GRÁFICOS")
            self.status_label.setText("")
            self._update_generate_button_availability()

    def on_generate_clicked(self):
        is_valid, message = self.validate_form()

        if not is_valid:
            QMessageBox.warning(self, "Validação", message)
            return

        input_data = build_input_data(self._analysis_input_values())

        self.set_processing_state(True)

        self._processing_thread = QThread()
        self._processing_worker = DataProcessingWorker(
            input_data,
            self.services.data_processing_service,
        )
        self._processing_worker.moveToThread(self._processing_thread)

        self._processing_thread.started.connect(self._processing_worker.run)
        self._processing_worker.finished.connect(self._on_processing_finished)
        self._processing_worker.error.connect(self._on_processing_error)
        self._processing_worker.finished.connect(self._processing_thread.quit)
        self._processing_worker.error.connect(self._processing_thread.quit)
        self._processing_thread.finished.connect(self._processing_worker.deleteLater)
        self._processing_thread.finished.connect(self._processing_thread.deleteLater)
        self._processing_thread.finished.connect(self._clear_processing_thread_refs)
        self._processing_thread.start()

    def _on_processing_finished(self, processed):
        try:
            # Mantém a barra visível enquanto a página de gráficos é renderizada.
            self.status_label.setText("Renderizando gráficos na interface. Aguarde...")
            if not self.main_window.set_processed_data(processed):
                QMessageBox.critical(
                    self,
                    "Erro ao montar gráficos",
                    self.services.error_service.friendly_graph_rendering_message(),
                )
                return
            self.main_window.show_graph_page()
        except Exception as exc:
            self.services.error_service.log_exception(exc, "Graph page rendering failed")
            QMessageBox.critical(
                self,
                "Erro ao montar gráficos",
                self.services.error_service.friendly_graph_rendering_message(),
            )
        finally:
            self.set_processing_state(False)

    def _on_processing_error(self, error_message: str):
        self.set_processing_state(False)
        self.services.error_service.log_exception(
            RuntimeError(error_message),
            "Data processing failed",
        )
        QMessageBox.critical(
            self,
            "Erro ao processar medição",
            self.services.error_service.friendly_processing_message(),
        )

    def _clear_processing_thread_refs(self):
        self._processing_thread = None
        self._processing_worker = None
