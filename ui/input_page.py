from pathlib import Path
import sys

from core.models import InputData
from core.excel_reader import process_input_data

try:
    from core.paths import get_app_assets
except Exception:
    get_app_assets = None


APP_VERSION_FALLBACK = "1.3.3"


def get_app_version() -> str:
    """
    Retorna a versão da aplicação no padrão SemVer.

    Em desenvolvimento, lê o arquivo VERSION na raiz do projeto.
    Em build PyInstaller --onedir, tenta ler VERSION ao lado do executável
    ou dentro da pasta _internal, quando incluído via --add-data.
    """
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        internal_dir = Path(getattr(sys, "_MEIPASS", executable_dir)).resolve()
        candidates.extend([
            executable_dir / "VERSION",
            internal_dir / "VERSION",
        ])
    else:
        candidates.append(Path(__file__).resolve().parents[1] / "VERSION")

    for version_file in candidates:
        try:
            if version_file.exists():
                version = version_file.read_text(encoding="utf-8").strip()
                if version:
                    return version
        except Exception:
            pass

    return APP_VERSION_FALLBACK


from PySide6.QtCore import Qt, QObject, Signal, Slot, QThread
from PySide6.QtGui import QPixmap
from ui.about_dialog import AboutDialog

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


class DataProcessingWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, input_data: InputData):
        super().__init__()
        self.input_data = input_data

    @Slot()
    def run(self):
        try:
            processed = process_input_data(self.input_data)
            self.finished.emit(processed)
        except Exception as exc:
            self.error.emit(str(exc))


class InputPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.selected_excel_path: Path | None = None
        self.assets = get_app_assets() if get_app_assets else None
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
        root_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

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
        form_card.setMaximumWidth(1200)
        form_card.setMinimumWidth(820)
        form_card.setStyleSheet("""
            QFrame {
                background-color: #000000;
                border: 1px solid #000000;
                border-radius: 12px;
            }
        """)

        form_layout = QVBoxLayout()
        form_layout.setContentsMargins(30, 24, 30, 24)
        form_layout.setSpacing(14)
        form_layout.addWidget(title)

        self.company_input = self._create_labeled_input("EMPRESA", "Ex.: ECOCEL")
        self.city_input = self._create_labeled_input("CIDADE/ES", "Ex.: VITÓRIA/ES")
        self.equipment_selector = self._create_equipment_selector()
        self.equipment_reference_input = self._create_labeled_input("REFERÊNCIA / TAG", "Ex.: TRAFO 01")
        self.equipment_value_input = self._create_labeled_input("POTÊNCIA (kVA)", "Ex.: 500")
        self.local_input = self._create_labeled_input("LOCAL", "Ex.: LADO FONTE ou LADO CARGA")
        self.revision_input = self._create_labeled_input("REVISÃO", "Ex.: 00")

        self.file_label_title = QLabel("ARQUIVO DE DADOS")
        self.file_label_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label_title.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #f1f1f1;
            background-color: transparent;
        """)

        self.file_path_label = QLabel("Nenhum arquivo selecionado")
        self.file_path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_path_label.setWordWrap(True)
        self.file_path_label.setStyleSheet("""
            color: #d0d0d0;
            background-color: #101010;
            border: 1px solid #101010;
            border-radius: 8px;
            padding: 10px;
            font-size: 13px;
        """)

        self.select_file_button = QPushButton("SELECIONAR ARQUIVO - PRIMATA/EMBRASUL")
        self.select_file_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_file_button.setStyleSheet("""
            QPushButton {
                background-color: #2d7d46;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 14px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #25673a;
            }
            QPushButton:disabled {
                background-color: #1f5131;
                color: #d0d0d0;
            }
        """)
        self.select_file_button.clicked.connect(self.select_data_file)

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

        form_layout.addLayout(top_row_layout)
        form_layout.addLayout(equipment_row_layout)
        form_layout.addLayout(data_row_layout)
        form_layout.addSpacing(4)
        form_layout.addWidget(self.file_label_title)
        form_layout.addWidget(self.file_path_label)
        form_layout.addWidget(self.select_file_button)
        form_layout.addSpacing(8)
        form_layout.addWidget(self.generate_button)
        form_layout.addWidget(self.status_label)
        form_layout.addWidget(self.progress_bar)

        logos_layout = self._create_logos_layout()
        if logos_layout:
            form_layout.addSpacing(8)
            form_layout.addLayout(logos_layout)

        self.version_label = ClickableLabel()
        self.version_label.setText(f"v{get_app_version()}")
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

        form_layout.addSpacing(2)
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
        scroll_container.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout()
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        scroll_layout.addWidget(form_card)
        scroll_container.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_container)

        root_layout.addWidget(scroll_area)
        self.setLayout(root_layout)

    def _enable_uppercase_input(self, line_edit: QLineEdit):
        def force_uppercase(value: str):
            cursor_position = line_edit.cursorPosition()
            upper_value = value.upper()
            if value != upper_value:
                line_edit.setText(upper_value)
                line_edit.setCursorPosition(cursor_position)

        line_edit.textEdited.connect(force_uppercase)

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

    def _create_logos_layout(self):
        logos_layout = QHBoxLayout()
        logos_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logos_layout.setSpacing(28)

        primata_logo = self._create_logo_widget(
            logo_attr="primata_logo",
            fallback_filename="primata_logo.png",
            tooltip="Clique para visualizar a colinha do Primata",
            callback=self.show_primata_cola,
            width=170,
            height=60,
        )

        embrasul_logo = self._create_logo_widget(
            logo_attr="embrasul_logo",
            fallback_filename="embrasul_logo.png",
            tooltip="Clique para visualizar a colinha da Embrasul",
            callback=self.show_embrasul_cola,
            width=170,
            height=60,
        )

        has_any_logo = False

        if primata_logo:
            logos_layout.addWidget(primata_logo)
            has_any_logo = True

        if embrasul_logo:
            logos_layout.addWidget(embrasul_logo)
            has_any_logo = True

        return logos_layout if has_any_logo else None

    def _create_logo_widget(
        self,
        logo_attr: str,
        fallback_filename: str,
        tooltip: str,
        callback,
        width: int = 170,
        height: int = 60,
    ):
        logo_path = None

        if self.assets and getattr(self.assets, logo_attr, None):
            logo_path = getattr(self.assets, logo_attr)

        if not logo_path:
            logo_path = Path(__file__).resolve().parent.parent / "assets" / fallback_filename

        if not logo_path or not Path(logo_path).exists():
            return None

        pixmap = QPixmap(str(logo_path))
        if pixmap.isNull():
            return None

        logo_label = ClickableLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setToolTip(tooltip)
        logo_label.setPixmap(
            pixmap.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        logo_label.set_click_callback(callback)

        return logo_label

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
            cola_path = Path(__file__).resolve().parent.parent / "assets" / fallback_filename

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
            app_version=get_app_version(),
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
            "Selecionar arquivo de dados",
            "",
            "Arquivos de dados (*.xlsx *.txt);;Planilha Primata (*.xlsx);;Texto Embrasul (*.txt)"
        )

        if file_path:
            self.selected_excel_path = Path(file_path)
            self.file_path_label.setText(str(self.selected_excel_path))

    def normalize_inputs(self):
        self.company_input["input"].setText(self.company_input["input"].text().strip().upper())
        self.city_input["input"].setText(self.city_input["input"].text().strip().upper())
        self.equipment_reference_input["input"].setText(
            self.equipment_reference_input["input"].text().strip().upper()
        )
        self.local_input["input"].setText(self.local_input["input"].text().strip().upper())
        self.revision_input["input"].setText(self.revision_input["input"].text().strip())

        equipment_value_text = self.equipment_value_input["input"].text().strip().replace(",", ".")
        self.equipment_value_input["input"].setText(equipment_value_text)

    def validate_form(self) -> tuple[bool, str]:
        self.normalize_inputs()

        company = self.company_input["input"].text()
        city = self.city_input["input"].text()
        equipment_type = self.get_equipment_type()
        equipment_reference = self.equipment_reference_input["input"].text()
        equipment_value = self.equipment_value_input["input"].text()
        local = self.local_input["input"].text()
        revision = self.revision_input["input"].text()

        if not company:
            return False, "Informe a EMPRESA."
        if not city:
            return False, "Informe a CIDADE/ES."
        if not equipment_reference:
            return False, "Informe a REFERÊNCIA / TAG do equipamento."
        if not equipment_value:
            return False, "Informe a POTÊNCIA do transformador." if equipment_type == "TRAFO" else "Informe a CORRENTE do disjuntor."
        if not local:
            return False, "Informe o LOCAL."
        if not revision:
            return False, "Informe a REVISÃO."
        if self.selected_excel_path is None:
            return False, "Selecione o arquivo de dados."
        if self.selected_excel_path.suffix.lower() not in [".xlsx", ".txt"]:
            return False, "O arquivo selecionado deve ser .xlsx ou .txt."

        try:
            numeric_equipment_value = float(equipment_value)
        except ValueError:
            return False, "O campo POTÊNCIA deve ser numérico." if equipment_type == "TRAFO" else "O campo CORRENTE deve ser numérico."

        if numeric_equipment_value <= 0:
            return False, "A POTÊNCIA deve ser maior que zero." if equipment_type == "TRAFO" else "A CORRENTE deve ser maior que zero."

        if not revision.isdigit():
            return False, "O campo REVISÃO deve conter apenas números."

        return True, ""

    def set_processing_state(self, processing: bool):
        self.generate_button.setDisabled(processing)
        self.select_file_button.setDisabled(processing)

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

    def on_generate_clicked(self):
        is_valid, message = self.validate_form()

        if not is_valid:
            QMessageBox.warning(self, "Validação", message)
            return

        input_data = InputData(
            company=self.company_input["input"].text(),
            city=self.city_input["input"].text(),
            equipment_type=self.get_equipment_type(),
            equipment_reference=self.equipment_reference_input["input"].text(),
            equipment_value=float(self.equipment_value_input["input"].text()),
            local=self.local_input["input"].text(),
            revision=self.revision_input["input"].text(),
            excel_path=self.selected_excel_path,
        )

        self.set_processing_state(True)

        self._processing_thread = QThread()
        self._processing_worker = DataProcessingWorker(input_data)
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
            self.main_window.set_processed_data(processed)
            self.main_window.show_graph_page()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Erro",
                f"Erro ao renderizar os gráficos:\n\n{str(exc)}"
            )
        finally:
            self.set_processing_state(False)

    def _on_processing_error(self, error_message: str):
        self.set_processing_state(False)
        QMessageBox.critical(
            self,
            "Erro",
            f"Erro ao processar os dados:\n\n{error_message}"
        )

    def _clear_processing_thread_refs(self):
        self._processing_thread = None
        self._processing_worker = None
