from PySide6.QtWidgets import QMainWindow, QStackedWidget

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
        self.setMinimumSize(1100, 700)

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

    def show_input_page(self):
        self.stack.setCurrentWidget(self.input_page)

    def show_graph_page(self):
        if self.processed_data is None:
            return

        self.stack.setCurrentWidget(self.graph_page)