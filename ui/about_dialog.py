import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
)


class AboutDialog(QDialog):

    def __init__(
        self,
        parent=None,
        app_version="1.0.0",
        available_update=None
    ):
        super().__init__(parent)

        self.available_update = available_update

        print("\n[ABOUT DIALOG]")
        print("available_update:")
        print(self.available_update)

        self.setWindowTitle("Sobre o MUG")
        self.setFixedSize(520, 420)

        self.setStyleSheet("""
            QDialog {
                background-color: #000000;
                color: #f1f1f1;
            }

            QLabel {
                color: #f1f1f1;
                font-size: 12px;
            }

            QPushButton {
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-weight: bold;
                min-width: 120px;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("MUG")

        title.setStyleSheet("""
            font-size: 34px;
            font-weight: bold;
            color: white;
        """)

        content = QLabel(
            f"Monitoramento e Análise Gráfica de Grandezas Elétricas<br><br>"
            f"<b>Versão:</b> v{app_version}<br>"
            f"<b>Copyright:</b> (C) 2026 ECOCEL<br><br>"
            f"Aplicação desktop para análise gráfica de grandezas elétricas, "
            f"processamento de arquivos Primata/Embrasul e exportação de gráficos em PDF.<br><br>"
            f"<b>Tecnologias:</b><br>"
            f"Python, PySide6, Plotly, Pandas, Kaleido e Chromium embarcado.<br><br>"
            f"<b>Repositório:</b><br>"
            f"https://github.com/pancotto/MUG"
        )

        content.setWordWrap(True)
        content.setTextFormat(Qt.TextFormat.RichText)
        content.setOpenExternalLinks(True)

        layout.addWidget(title)
        layout.addWidget(content)

        # ============================================
        # STATUS DE ATUALIZAÇÃO
        # ============================================

        if self.available_update:

            update_label = QLabel(
                f"Nova versão disponível: "
                f"v{self.available_update['version']}"
            )

            update_label.setStyleSheet("""
                color: #4CAF50;
                font-size: 13px;
                font-weight: bold;
                margin-top: 10px;
            """)

            layout.addWidget(update_label)

            download_button = QPushButton(
                "BAIXAR ATUALIZAÇÃO"
            )

            download_button.setStyleSheet("""
                QPushButton {
                    background-color: #2d7d46;
                }

                QPushButton:hover {
                    background-color: #25673a;
                }
            """)

            download_button.clicked.connect(
                lambda: webbrowser.open(
                    self.available_update["html_url"]
                )
            )

            layout.addWidget(download_button)

        else:

            updated_label = QLabel(
                "✓ Aplicação atualizada<br>"
                "Você está utilizando a versão mais recente do MUG."
            )

            updated_label.setTextFormat(
                Qt.TextFormat.RichText
            )

            updated_label.setStyleSheet("""
                color: #2d7d46;
                font-size: 13px;
                font-weight: bold;
                margin-top: 10px;
            """)

            layout.addWidget(updated_label)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        close_button = QPushButton("FECHAR")

        close_button.setStyleSheet("""
            QPushButton {
                background-color: #2d6cdf;
            }

            QPushButton:hover {
                background-color: #1f5fbf;
            }
        """)

        close_button.clicked.connect(self.accept)

        buttons_layout.addWidget(close_button)

        layout.addStretch()
        layout.addLayout(buttons_layout)

        self.setLayout(layout)
