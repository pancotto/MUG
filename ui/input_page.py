from pathlib import Path

from core.models import InputData
from core.excel_reader import process_input_data

try:
    from core.paths import get_app_assets
except Exception:
    get_app_assets = None

from PySide6.QtCore import Qt, QObject, Signal, Slot, QThread
from PySide6.QtGui import QPixmap
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
        root_layout.setContentsMargins(40, 30, 40, 30)
        root_layout.setSpacing(20)
        root_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("ANALISADOR GRÁFICO DE GRANDEZAS ELÉTRICAS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            color: #ffffff;
            margin-bottom: 10px;
            background-color: #000000;
            padding: 6px;
        """)

        form_card = QFrame()
        form_card.setMaximumWidth(1200)
        form_card.setStyleSheet("""
            QFrame {
                background-color: #000000;
                border: 1px solid #000000;
                border-radius: 12px;
            }
        """)

        form_layout = QVBoxLayout()
        form_layout.setContentsMargins(30, 25, 30, 25)
        form_layout.setSpacing(16)

        self.company_input = self._create_labeled_input("EMPRESA", "Ex.: ECOCEL")
        self.city_input = self._create_labeled_input("CIDADE/ES", "Ex.: VITÓRIA/ES")
        self.trafo_input = self._create_labeled_input("TRAFO (kVA)", "Ex.: 1500")
        self.local_input = self._create_labeled_input("LOCAL", "Ex.: QGBT")
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

        form_layout.addWidget(self.company_input["container"])
        form_layout.addWidget(self.city_input["container"])
        form_layout.addWidget(self.trafo_input["container"])
        form_layout.addWidget(self.local_input["container"])
        form_layout.addWidget(self.revision_input["container"])
        form_layout.addWidget(self.file_label_title)
        form_layout.addWidget(self.file_path_label)
        form_layout.addWidget(self.select_file_button)
        form_layout.addSpacing(10)
        form_layout.addWidget(self.generate_button)
        form_layout.addWidget(self.status_label)
        form_layout.addWidget(self.progress_bar)

        logos_layout = self._create_logos_layout()
        if logos_layout:
            form_layout.addSpacing(8)
            form_layout.addLayout(logos_layout)

        form_card.setLayout(form_layout)

        root_layout.addWidget(title)
        root_layout.addWidget(form_card)
        self.setLayout(root_layout)

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
        self.local_input["input"].setText(self.local_input["input"].text().strip().upper())
        self.revision_input["input"].setText(self.revision_input["input"].text().strip())

        trafo_text = self.trafo_input["input"].text().strip().replace(",", ".")
        self.trafo_input["input"].setText(trafo_text)

    def validate_form(self) -> tuple[bool, str]:
        self.normalize_inputs()

        company = self.company_input["input"].text()
        city = self.city_input["input"].text()
        trafo = self.trafo_input["input"].text()
        local = self.local_input["input"].text()
        revision = self.revision_input["input"].text()

        if not company:
            return False, "Informe a EMPRESA."
        if not city:
            return False, "Informe a CIDADE/ES."
        if not trafo:
            return False, "Informe o TRAFO."
        if not local:
            return False, "Informe o LOCAL."
        if not revision:
            return False, "Informe a REVISÃO."
        if self.selected_excel_path is None:
            return False, "Selecione o arquivo de dados."
        if self.selected_excel_path.suffix.lower() not in [".xlsx", ".txt"]:
            return False, "O arquivo selecionado deve ser .xlsx ou .txt."

        try:
            float(trafo)
        except ValueError:
            return False, "O campo TRAFO deve ser numérico."

        if not revision.isdigit():
            return False, "O campo REVISÃO deve conter apenas números."

        return True, ""

    def set_processing_state(self, processing: bool):
        self.generate_button.setDisabled(processing)
        self.select_file_button.setDisabled(processing)

        for field in [
            self.company_input["input"],
            self.city_input["input"],
            self.trafo_input["input"],
            self.local_input["input"],
            self.revision_input["input"],
        ]:
            field.setDisabled(processing)

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
            trafo=float(self.trafo_input["input"].text()),
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
