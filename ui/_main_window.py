from PySide6.QtCore import Qt
import webbrowser

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox

from ui.input_page import InputPage
from ui.graph_page import GraphPage, get_app_version
from core.update_checker import UpdateChecker
from ui.about_dialog import AboutDialog


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

        self.available_update = None
        self.check_for_updates()

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

        self.graph_page.clear_loaded_data()

        self.show_input_page()

        self.available_update = None

        self.check_for_updates()

    def show_input_page(self):
        self.stack.setCurrentWidget(self.input_page)

    def show_graph_page(self):

        if self.processed_data is None:
            return

        self.stack.setCurrentWidget(self.graph_page)

    def check_for_updates(self):

        try:

            current_version = get_app_version()

            update = UpdateChecker.is_update_available(
                current_version
            )

            self.available_update = update

            if not update:
                return

            message = (
                f"Nova versão disponível!\n\n"
                f"Versão atual: v{current_version}\n"
                f"Nova versão: v{update['version']}\n\n"
                f"Deseja acessar a página de download?"
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

                webbrowser.open(update["html_url"])

        except Exception as e:

            print(f"[UPDATE CHECK ERROR] {e}")
