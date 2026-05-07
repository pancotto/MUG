from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox

from ui.input_page import InputPage
from ui.graph_page import GraphPage


class MainWindow(QMainWindow):
    """
    Janela principal da aplicação desktop.
    """

    def __init__(self):
        super().__init__()

        self.processed_data = None

        self.setWindowTitle("ANALISADOR GRÁFICO DE GRANDEZAS ELÉTRICAS")
        self.resize(1400, 900)
        self.setMinimumSize(1180, 760)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.input_page = InputPage(self)
        self.graph_page = GraphPage(self)

        self.stack.addWidget(self.input_page)
        self.stack.addWidget(self.graph_page)

        self.show_input_page()

    def set_processed_data(self, processed):
        self.processed_data = processed
        self.graph_page.load_processed_data(processed)

    def start_new_analysis(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Nova análise")
        msg_box.setText(
            "Deseja iniciar uma nova análise?\n\n"
            "Os gráficos atuais serão descartados."
        )

        sim_button = msg_box.addButton("Sim", QMessageBox.ButtonRole.YesRole)
        nao_button = msg_box.addButton("Não", QMessageBox.ButtonRole.NoRole)

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

            QPushButton {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 6px 16px;
                min-width: 80px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #3a3a3a;
            }

            QPushButton:pressed {
                background-color: #1f1f1f;
            }
        """)

        msg_box.exec()

        if msg_box.clickedButton() != sim_button:
            return

        self.processed_data = None
        self.graph_page.clear_loaded_data()
        self.show_input_page()

    def show_input_page(self):
        self.stack.setCurrentWidget(self.input_page)

    def show_graph_page(self):
        if self.processed_data is None:
            return

        self.stack.setCurrentWidget(self.graph_page)