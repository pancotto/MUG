from pathlib import Path
import sys
import tempfile
import json

import pandas as pd
import plotly.graph_objects as go

from PySide6.QtCore import QObject, QUrl, Signal, Slot, QThread, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QMessageBox,
    QLabel,
    QPushButton,
    QCheckBox,
    QScrollArea,
    QFileDialog,
    QProgressBar,
)
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView

from core.graph_builder import (
    create_tension_graph,
    create_current_graph,
    create_active_power_graph,
    create_consumption_graph,
    create_apparent_power_graph,
    create_pf_graph,
    create_tension_imbalance_graph,
    create_current_imbalance_graph,
    create_dht_voltage_graph,
    create_dht_current_graph,
    create_combined_vxi_graph,
    create_combined_kwxkva_graph,
)
from core.models import ProcessedData
from core.phase_sync import (
    apply_phase_visibility_to_figure,
    default_phase_visibility,
    get_current_extreme_marker_updates,
    get_phase_trace_updates,
    get_sync_trace_names,
    get_trace_phase,
    is_phase_sync_graph,
    update_phase_extreme_traces,
)
from core.profiling import profile_block, log_profile_event
from ui.about_dialog import AboutDialog


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


DEFAULT_PDF_GRAPHS = {
    "Tensão",
    "Corrente",
    "Potência Ativa",
    "Potência Aparente",
    "Fator de Potência",
    "DHT Tensão",
    "DHT Corrente",
}


GRAPH_EXPORT_ORDER = [
    "Tensão",
    "Corrente",
    "Potência Ativa",
    "Potência Aparente",
    "Fator de Potência",
    "DHT Tensão",
    "DHT Corrente",
    "Deseq. Tensão",
    "Deseq. Corrente",
    "Consumo",
    "Tensão x Corrente",
    "kW x kVA",
]



TAB_DISPLAY_NAMES = {
    "Tensão": "TENSÃO (V)",
    "Corrente": "CORRENTE (I)",
    "Potência Ativa": "POT. ATIVA (kW)",
    "Potência Aparente": "POT. APARENTE (kVA)",
    "Fator de Potência": "FATOR DE POTÊNCIA",
    "DHT Tensão": "DHT TENSÃO",
    "DHT Corrente": "DHT CORRENTE",
    "Deseq. Tensão": "DESEQ. TENSÃO",
    "Deseq. Corrente": "DESEQ. CORRENTE",
    "Consumo": "CONSUMO (kWh)",
    "Tensão x Corrente": "(V) x (I)",
    "kW x kVA": "(kW) x (kVA)",
}


FIXED_Y_SUBDIVISIONS = 20

FIXED_Y_GRAPHS = [
    "Tensão",
    "Corrente",
    "Potência Ativa",
    "Potência Aparente",
    "Deseq. Tensão",
    "Deseq. Corrente",
    "Consumo",
    "DHT Tensão",
    "DHT Corrente",
    "Tensão x Corrente",
    "kW x kVA",
]


def build_tick_values_high_density(dataframe: pd.DataFrame, x_min=None, x_max=None):
    if dataframe is None or dataframe.empty or "Datetime" not in dataframe.columns:
        return None, None, None, None

    df = dataframe.copy()
    df["Datetime"] = pd.to_datetime(df["Datetime"])

    x_min = df["Datetime"].min() if x_min is None else pd.to_datetime(x_min)
    x_max = df["Datetime"].max() if x_max is None else pd.to_datetime(x_max)

    df_filtered = df[(df["Datetime"] >= x_min) & (df["Datetime"] <= x_max)].copy()

    if df_filtered.empty:
        return None, None, None, None

    datetimes = list(df_filtered["Datetime"].drop_duplicates().sort_values())

    if len(datetimes) < 2:
        tickvals = datetimes
        ticktext = [dt.strftime("%d/%m - %H:%M:%S") for dt in datetimes]
        return tickvals, ticktext, x_min, x_max

    target_ticks = 50
    step = max(1, len(datetimes) // target_ticks)

    tickvals = datetimes[::step]

    if tickvals[-1] != datetimes[-1]:
        if len(tickvals) >= 2:
            last_gap = (datetimes[-1] - tickvals[-1]).total_seconds()
            ref_gap = (tickvals[-1] - tickvals[-2]).total_seconds()

            if ref_gap <= 0:
                ref_gap = last_gap

            if last_gap >= ref_gap * 0.6:
                tickvals.append(datetimes[-1])
        else:
            tickvals.append(datetimes[-1])

    ticktext = [dt.strftime("%d/%m - %H:%M:%S") for dt in tickvals]
    return tickvals, ticktext, x_min, x_max


def apply_default_x_density(fig: go.Figure, dataframe: pd.DataFrame, x_min=None, x_max=None):
    tickvals, ticktext, x_min, x_max = build_tick_values_high_density(dataframe, x_min, x_max)

    if tickvals and ticktext:
        fig.update_xaxes(
            range=[x_min, x_max],
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            tickangle=270,
        )

    return fig


def apply_fixed_y_subdivisions(fig: go.Figure):
    """
    Ajusta todos os eixos Y para quantidade fixa de subdivisões.
    Funciona também para gráficos com eixo duplo: yaxis, yaxis2, etc.
    """
    try:
        axis_values = {}

        for trace in fig.data:
            y_values = getattr(trace, "y", None)
            if y_values is None:
                continue

            values = pd.to_numeric(pd.Series(y_values), errors="coerce").dropna()
            if values.empty:
                continue

            axis_ref = getattr(trace, "yaxis", None) or "y"
            layout_axis = "yaxis" if axis_ref == "y" else f"yaxis{axis_ref.replace('y', '')}"

            axis_values.setdefault(layout_axis, []).extend(values.tolist())

        for layout_axis, values in axis_values.items():
            if layout_axis not in fig.layout:
                continue

            axis = fig.layout[layout_axis]

            if axis.range is not None:
                y_min = axis.range[0]
                y_max = axis.range[1]
            else:
                if not values:
                    continue

                y_min = min(values)
                y_max = max(values)

                if y_max <= y_min:
                    continue

                padding = (y_max - y_min) * 0.10

                final_y_min = y_min - padding
                final_y_max = y_max + padding

                y_min = max(0, final_y_min)
                y_max = final_y_max

                axis.range = [y_min, y_max]
                axis.autorange = False

            y_range = y_max - y_min
            if y_range <= 0:
                continue

            dtick = y_range / FIXED_Y_SUBDIVISIONS

            axis.tickmode = "linear"
            axis.tick0 = y_min
            axis.dtick = dtick

    except Exception:
        pass

    return fig


def apply_zoom_y_autorange(fig: go.Figure):
    """
    No modo zoom, ajusta o eixo Y somente com base nos dados medidos,
    ignorando linhas horizontais de limite, nominal, adequada, crítica etc.
    O resultado é travado na quantidade fixa de subdivisões.
    """

    def is_limit_or_reference_trace(trace) -> bool:
        name = str(getattr(trace, "name", "") or "").lower()

        reference_keywords = [
            "nominal",
            "limite",
            "adequada",
            "precária",
            "precaria",
            "crítica",
            "critica",
            "faixa",
        ]

        if any(keyword in name for keyword in reference_keywords):
            return True

        y_values = getattr(trace, "y", None)
        if y_values is None:
            return False

        values = pd.to_numeric(pd.Series(y_values), errors="coerce").dropna()

        if len(values) > 5 and values.nunique() <= 2:
            return True

        return False

    try:
        axis_values = {}

        for trace in fig.data:
            if is_limit_or_reference_trace(trace):
                continue

            y_values = getattr(trace, "y", None)
            if y_values is None:
                continue

            values = pd.to_numeric(pd.Series(y_values), errors="coerce").dropna()
            if values.empty:
                continue

            axis_ref = getattr(trace, "yaxis", None) or "y"
            layout_axis = "yaxis" if axis_ref == "y" else f"yaxis{axis_ref.replace('y', '')}"

            axis_values.setdefault(layout_axis, []).extend(values.tolist())

        for layout_axis, values in axis_values.items():
            if layout_axis not in fig.layout:
                continue

            if not values:
                continue

            y_min = min(values)
            y_max = max(values)

            if y_max <= y_min:
                continue

            y_range = y_max - y_min
            padding = y_range * 0.10

            final_y_min = y_min - padding
            final_y_max = y_max + padding

            if final_y_min >= 0:
                y_min = final_y_min
            else:
                y_min = 0

            y_max = final_y_max

            final_y_range = y_max - y_min
            if final_y_range <= 0:
                continue

            dtick = final_y_range / FIXED_Y_SUBDIVISIONS

            fig.layout[layout_axis].autorange = False
            fig.layout[layout_axis].range = [y_min, y_max]
            fig.layout[layout_axis].tickmode = "linear"
            fig.layout[layout_axis].tick0 = y_min
            fig.layout[layout_axis].dtick = dtick

    except Exception:
        pass

    return fig


class PlotBridge(QObject):
    zoomChanged = Signal(str, str, str)
    phaseLegendToggled = Signal(str, str, bool)

    @Slot(str, str, str)
    def onZoomChanged(self, source_name, x_min, x_max):
        self.zoomChanged.emit(source_name, x_min, x_max)

    @Slot(str, str, bool)
    def onPhaseLegendToggled(self, source_name, trace_name, visible):
        self.phaseLegendToggled.emit(source_name, trace_name, visible)


class PdfExportWorker(QObject):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, processed, selected_graphs, output_dir, zoom_mode, phase_visibility=None):
        super().__init__()
        self.processed = processed
        self.selected_graphs = selected_graphs
        self.output_dir = output_dir
        self.zoom_mode = zoom_mode
        self.phase_visibility = phase_visibility

    @Slot()
    def run(self):
        try:
            from core.pdf_exporter import export_figures_to_pdf

            pdf_path = export_figures_to_pdf(
                processed=self.processed,
                selected_graphs=self.selected_graphs,
                output_dir=self.output_dir,
                zoom_mode=self.zoom_mode,
                phase_visibility=self.phase_visibility,
            )
            self.finished.emit(str(pdf_path))
        except Exception as exc:
            self.error.emit(str(exc))


class PdfExportTab(QWidget):
    def __init__(self, graph_page):
        super().__init__()
        self.graph_page = graph_page
        self.checkboxes: dict[str, QCheckBox] = {}
        self.default_pdf_graphs = DEFAULT_PDF_GRAPHS
        self._pdf_thread: QThread | None = None
        self._pdf_worker: PdfExportWorker | None = None
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                color: #f1f1f1;
                font-family: Arial;
            }
            QLabel {
                color: #f1f1f1;
                background-color: #000000;
            }
            QCheckBox {
                background-color: #000000;
                color: #f1f1f1;
                font-size: 13px;
                padding: 4px 0;
            }
            QPushButton {
                background-color: #2d7d46;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 18px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #25673a;
            }
            QPushButton:disabled {
                background-color: #1f5131;
                color: #d0d0d0;
            }
            QScrollArea {
                border: 1px solid #000000;
                background-color: #000000;
                border-radius: 8px;
            }
            QScrollArea QWidget {
                background-color: #000000;
            }
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

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(16)

        title = QLabel("EXPORTAR PDF")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")

        subtitle = QLabel(
            "Selecione os gráficos que deseja incluir no PDF. "
            "O arquivo será gerado em formato A4 horizontal, com um gráfico por página."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; color: #bbbbbb;")

        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        self.status_label.setStyleSheet("font-size: 13px; color: #bbbbbb; font-weight: bold;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("Gerando PDF... aguarde")
        self.progress_bar.setVisible(False)

        self.select_default_button = QPushButton("SELEÇÃO PADRÃO")
        self.select_default_button.setStyleSheet("""
            QPushButton {
                background-color: #2d7d46;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 18px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #25673a;
            }
            QPushButton:disabled {
                background-color: #1f5131;
                color: #d0d0d0;
            }
        """)
        self.select_default_button.clicked.connect(self.select_default)

        self.select_all_button = QPushButton("SELECIONAR TODOS")
        self.select_all_button.setStyleSheet("""
            QPushButton {
                background-color: #2d7d46;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 18px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #25673a;
            }
            QPushButton:disabled {
                background-color: #1f5131;
                color: #d0d0d0;
            }
        """)
        self.select_all_button.clicked.connect(self.select_all)

        self.clear_all_button = QPushButton("LIMPAR SELEÇÃO")
        self.clear_all_button.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 18px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:disabled {
                background-color: #303030;
                color: #b0b0b0;
            }
        """)
        self.clear_all_button.clicked.connect(self.clear_all)

        self.export_button = QPushButton("EXPORTAR PDF")
        self.export_button.setStyleSheet("""
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
        self.export_button.clicked.connect(self.export_pdf)

        buttons_layout = QVBoxLayout()
        buttons_layout.addWidget(self.select_default_button)
        buttons_layout.addWidget(self.select_all_button)
        buttons_layout.addWidget(self.clear_all_button)
        buttons_layout.addWidget(self.export_button)
        buttons_layout.addWidget(self.status_label)
        buttons_layout.addWidget(self.progress_bar)

        checklist_container = QWidget()
        checklist_layout = QVBoxLayout()
        checklist_layout.setContentsMargins(0, 0, 0, 0)
        checklist_layout.setSpacing(8)

        for graph_name in GRAPH_EXPORT_ORDER:
            checkbox = QCheckBox(graph_name)
            checkbox.setChecked(graph_name in self.default_pdf_graphs)
            self.checkboxes[graph_name] = checkbox
            checklist_layout.addWidget(checkbox)

        checklist_layout.addStretch()
        checklist_container.setLayout(checklist_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(checklist_container)

        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)
        root_layout.addWidget(scroll_area)
        root_layout.addLayout(buttons_layout)

        self.setLayout(root_layout)

    def set_exporting_state(self, exporting: bool):
        self.export_button.setDisabled(exporting)
        self.select_default_button.setDisabled(exporting)
        self.select_all_button.setDisabled(exporting)
        self.clear_all_button.setDisabled(exporting)

        for checkbox in self.checkboxes.values():
            checkbox.setDisabled(exporting)

        self.progress_bar.setVisible(exporting)
        self.status_label.setVisible(exporting)

        if exporting:
            self.export_button.setText("EXPORTANDO PDF...")
            self.status_label.setText("Processando gráficos e montando o arquivo PDF. Aguarde...")
        else:
            self.export_button.setText("EXPORTAR PDF")
            self.status_label.setText("")

    def select_default(self):
        for graph_name, checkbox in self.checkboxes.items():
            checkbox.setChecked(graph_name in self.default_pdf_graphs)

    def select_all(self):
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)

    def clear_all(self):
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)

    def export_pdf(self):
        selected_graphs = [
            name for name, checkbox in self.checkboxes.items()
            if checkbox.isChecked()
        ]

        if not selected_graphs:
            QMessageBox.warning(
                self,
                "Exportar PDF",
                "Selecione pelo menos um gráfico para exportação."
            )
            return

        if not self.graph_page.current_processed:
            QMessageBox.warning(
                self,
                "Exportar PDF",
                "Nenhum gráfico foi carregado ainda."
            )
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de destino do PDF"
        )

        if not output_dir:
            return

        try:
            processed = self.graph_page.current_processed

            zoom_mode = (
                self.graph_page.current_x_min is not None
                and self.graph_page.current_x_max is not None
            )

            if zoom_mode:
                df = processed.dataframe.copy()
                df["Datetime"] = pd.to_datetime(df["Datetime"])

                df = df[
                    (df["Datetime"] >= self.graph_page.current_x_min) &
                    (df["Datetime"] <= self.graph_page.current_x_max)
                ].copy()

                processed_for_pdf = ProcessedData(
                    company=processed.company,
                    city=processed.city,
                    trafo=processed.trafo,
                    local=processed.local,
                    revision=processed.revision,
                    excel_path=processed.excel_path,
                    dataframe=df,
                    integration_time=processed.integration_time,
                    tension=processed.tension,
                    equipment_type=processed.equipment_type,
                    equipment_reference=processed.equipment_reference,
                    equipment_value=processed.equipment_value,
                )
            else:
                processed_for_pdf = processed

            self.set_exporting_state(True)

            self._pdf_thread = QThread()
            self._pdf_worker = PdfExportWorker(
                processed=processed_for_pdf,
                selected_graphs=selected_graphs,
                output_dir=Path(output_dir),
                zoom_mode=zoom_mode,
                phase_visibility=self.graph_page.phase_visibility.copy(),
            )
            self._pdf_worker.moveToThread(self._pdf_thread)

            self._pdf_thread.started.connect(self._pdf_worker.run)
            self._pdf_worker.finished.connect(self._on_pdf_finished)
            self._pdf_worker.error.connect(self._on_pdf_error)
            self._pdf_worker.finished.connect(self._pdf_thread.quit)
            self._pdf_worker.error.connect(self._pdf_thread.quit)
            self._pdf_thread.finished.connect(self._pdf_worker.deleteLater)
            self._pdf_thread.finished.connect(self._pdf_thread.deleteLater)
            self._pdf_thread.finished.connect(self._clear_pdf_thread_refs)
            self._pdf_thread.start()

        except Exception as e:
            self.set_exporting_state(False)
            QMessageBox.critical(
                self,
                "Erro ao gerar PDF",
                f"Ocorreu um erro ao gerar o PDF:\n\n{str(e)}"
            )

    def _on_pdf_finished(self, pdf_path: str):
        self.set_exporting_state(False)
        QMessageBox.information(
            self,
            "PDF gerado",
            f"PDF gerado com sucesso:\n\n{pdf_path}"
        )

    def _on_pdf_error(self, error_message: str):
        self.set_exporting_state(False)
        QMessageBox.critical(
            self,
            "Erro ao gerar PDF",
            f"Ocorreu um erro ao gerar o PDF:\n\n{error_message}"
        )

    def _clear_pdf_thread_refs(self):
        self._pdf_thread = None
        self._pdf_worker = None

class GraphPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.current_processed: ProcessedData | None = None
        self.current_figures: dict[str, go.Figure] = {}
        self.webviews: dict[str, QWebEngineView] = {}

        self.syncing_zoom = False
        self.current_x_min = None
        self.current_x_max = None
        self.phase_visibility = default_phase_visibility()

        self.plot_bridge = PlotBridge()
        self.plot_bridge.zoomChanged.connect(self._on_zoom_changed)
        self.plot_bridge.phaseLegendToggled.connect(self._on_phase_legend_toggled)

        self._build_ui()


    def _build_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                color: #f1f1f1;
                font-family: Arial;
            }
            QTabWidget::pane {
                border: 1px solid #000000;
                background: #000000;
            }
            QTabBar::tab {
                background: #000000;
                color: #dcdcdc;
                padding: 8px 14px;
                margin-right: 1px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #2d6cdf;
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background: #333333;
            }
            QTabBar::tab:last {
                background: #1f5131;
                color: #ffffff;
                font-weight: bold;
            }
            QTabBar::tab:last:selected {
                background: #2d7d46;
                color: #ffffff;
                font-weight: bold;
            }
        """)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(5, 5, 5, 5)
        root_layout.setSpacing(6)

        self.tabs = QTabWidget()

        self.tab_definitions = {
            "Tensão": QWebEngineView(),
            "Corrente": QWebEngineView(),
            "Potência Ativa": QWebEngineView(),
            "Potência Aparente": QWebEngineView(),
            "Fator de Potência": QWebEngineView(),
            "DHT Tensão": QWebEngineView(),
            "DHT Corrente": QWebEngineView(),
            "Deseq. Tensão": QWebEngineView(),
            "Deseq. Corrente": QWebEngineView(),
            "Consumo": QWebEngineView(),
            "Tensão x Corrente": QWebEngineView(),
            "kW x kVA": QWebEngineView(),
        }

        for tab_name, webview in self.tab_definitions.items():
            self.tabs.addTab(webview, TAB_DISPLAY_NAMES.get(tab_name, tab_name))
            self.webviews[tab_name] = webview

        self.pdf_export_tab = PdfExportTab(self)
        self.export_pdf_tab_index = self.tabs.addTab(
            self.pdf_export_tab,
            "EXPORTAR PDF"
        )

        self._highlight_pdf_export_tab()
        self._add_version_label()

        root_layout.addWidget(self.tabs)
        self.setLayout(root_layout)

    def _highlight_pdf_export_tab(self):
        """Destaca a aba de exportação."""
        tab_bar = self.tabs.tabBar()

        tab_bar.setTabToolTip(
            self.export_pdf_tab_index,
            "Exportar os gráficos selecionados em PDF A4 horizontal"
        )

    def _add_version_label(self):
        """Exibe ações globais no canto superior direito."""

        corner_widget = QWidget()

        corner_layout = QHBoxLayout()
        corner_layout.setContentsMargins(0, 0, 0, 0)
        corner_layout.setSpacing(8)

        self.new_analysis_button = QPushButton("NOVA ANÁLISE")

        self.new_analysis_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.new_analysis_button.setToolTip(
            "Retornar à tela inicial para iniciar uma nova análise"
        )

        self.new_analysis_button.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background-color: #8b1e1e;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 14px;
            }

            QPushButton:hover {
                background-color: #a32626;
            }

            QPushButton:pressed {
                background-color: #6f1818;
            }
        """)

        self.new_analysis_button.clicked.connect(
            self.main_window.start_new_analysis
        )

        self.version_button = QPushButton(
            f"v{get_app_version()}"
        )

        self.version_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.version_button.setToolTip(
            "Clique para ver informações sobre o MUG"
        )

        self.version_button.setStyleSheet("""
            QPushButton {
                color: #f1f1f1;
                background-color: #000000;
                border: none;
                font-size: 11px;
                font-weight: bold;
                padding: 0 8px;
                text-align: right;
            }

            QPushButton:hover {
                color: #ffffff;
                text-decoration: underline;
                background-color: #111111;
            }

            QPushButton:pressed {
                color: #d0d0d0;
            }
        """)

        self.version_button.clicked.connect(
            self.show_about_dialog
        )

        corner_layout.addWidget(self.new_analysis_button)
        corner_layout.addWidget(self.version_button)

        corner_widget.setLayout(corner_layout)

        self.tabs.setCornerWidget(
            corner_widget,
            Qt.Corner.TopRightCorner
        )

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


    def _build_html_with_zoom_sync(self, fig: go.Figure, source_name: str):
            html = fig.to_html(full_html=True, include_plotlyjs=True, div_id="plot")
            sync_trace_names = json.dumps(get_sync_trace_names(source_name), ensure_ascii=False)

            extra_js = f"""
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script>
            (function() {{
                var syncTraceNames = new Set({sync_trace_names});

                function attachZoomHandler() {{
                    if (typeof qt === 'undefined' || !qt.webChannelTransport) {{
                        setTimeout(attachZoomHandler, 100);
                        return;
                    }}

                    new QWebChannel(qt.webChannelTransport, function(channel) {{
                        window.plotBridge = channel.objects.plotBridge;
                        var plot = document.getElementById('plot');

                        if (!plot || !plot.on) {{
                            setTimeout(attachZoomHandler, 100);
                            return;
                        }}

                        if (plot.__mugPhaseSyncAttached) {{
                            return;
                        }}
                        plot.__mugPhaseSyncAttached = true;

                        plot.on('plotly_relayout', function(eventdata) {{
                            if (!eventdata) return;

                            if (eventdata['xaxis.range[0]'] && eventdata['xaxis.range[1]']) {{
                                window.plotBridge.onZoomChanged(
                                    "{source_name}",
                                    eventdata['xaxis.range[0]'],
                                    eventdata['xaxis.range[1]']
                                );
                            }}
                            else if (eventdata['xaxis.autorange']) {{
                                window.plotBridge.onZoomChanged(
                                    "{source_name}",
                                    "__FULL_VIEW__",
                                    "__FULL_VIEW__"
                                );
                            }}
                        }});

                        plot.on('plotly_legendclick', function(eventdata) {{
                            if (!eventdata || eventdata.curveNumber === undefined) return true;

                            var trace = plot.data[eventdata.curveNumber];
                            if (!trace || !syncTraceNames.has(trace.name)) return true;

                            var currentlyVisible = trace.visible !== 'legendonly' && trace.visible !== false;
                            window.plotBridge.onPhaseLegendToggled(
                                "{source_name}",
                                trace.name,
                                !currentlyVisible
                            );
                            return false;
                        }});

                        plot.on('plotly_legenddoubleclick', function(eventdata) {{
                            if (!eventdata || eventdata.curveNumber === undefined) return true;

                            var trace = plot.data[eventdata.curveNumber];
                            if (!trace || !syncTraceNames.has(trace.name)) return true;

                            return false;
                        }});
                    }});
                }}

                window.addEventListener('load', function() {{
                    setTimeout(attachZoomHandler, 150);
                }});
            }})();
            </script>
            """

            return html.replace("</body>", extra_js + "</body>")

    def _render_webview_figure(self, tab_name: str, fig: go.Figure):
        with profile_block("Plotly render webview", graph=tab_name):
            html = self._build_html_with_zoom_sync(fig, tab_name)

            temp_file = Path(tempfile.gettempdir()) / (
                f"plot_{tab_name.replace(' ', '_').replace('.', '').replace('/', '_')}.html"
            )

            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(html)

            webview = self.webviews[tab_name]

            channel = QWebChannel(webview.page())
            channel.registerObject("plotBridge", self.plot_bridge)
            webview.page().setWebChannel(channel)

            webview.load(QUrl.fromLocalFile(str(temp_file)))

    def _apply_phase_visibility_to_figures(self, figures: dict[str, go.Figure]):
        for graph_name, fig in figures.items():
            apply_phase_visibility_to_figure(
                fig=fig,
                graph_name=graph_name,
                phase_visibility=self.phase_visibility,
            )
            update_phase_extreme_traces(fig, graph_name)

    def _sync_phase_visibility_to_webviews(self, source_name: str | None = None):
        synced_graphs: list[str] = []
        affected_traces: list[str] = []

        for graph_name, fig in self.current_figures.items():
            if not is_phase_sync_graph(graph_name):
                continue

            updates = get_phase_trace_updates(fig, graph_name, self.phase_visibility)
            if not updates:
                continue

            indices = [update["index"] for update in updates]
            visible_values = [
                True if update["visible"] else "legendonly"
                for update in updates
            ]
            extreme_updates = get_current_extreme_marker_updates(fig)
            affected_traces.extend(
                f"{graph_name}:{update['trace']}->{update['phase']}={update['visible']}"
                for update in updates
            )

            script = f"""
            (function() {{
                var plot = document.getElementById('plot');
                if (!plot || typeof Plotly === 'undefined') return 'plot-not-ready';
                Plotly.restyle(
                    plot,
                    {{visible: {json.dumps(visible_values, ensure_ascii=False)}}},
                    {json.dumps(indices)}
                );
                var extremeUpdates = {json.dumps(extreme_updates, ensure_ascii=False, default=str)};
                extremeUpdates.forEach(function(update) {{
                    Plotly.restyle(
                        plot,
                        {{
                            x: [update.x],
                            y: [update.y],
                            text: [update.text],
                            hovertemplate: [update.hovertemplate]
                        }},
                        [update.index]
                    );
                }});
                return 'ok';
            }})();
            """

            webview = self.webviews.get(graph_name)
            if webview is None:
                continue

            webview.page().runJavaScript(script)
            synced_graphs.append(graph_name)

    def _on_phase_legend_toggled(self, source_name: str, trace_name: str, visible: bool):
        phase = get_trace_phase(source_name, trace_name)

        if phase is None:
            return

        next_visibility = self.phase_visibility.copy()
        next_visibility[phase] = visible

        if not any(next_visibility.values()):
            self._sync_phase_visibility_to_webviews(source_name=source_name)
            return

        self.phase_visibility = next_visibility
        self._apply_phase_visibility_to_figures(self.current_figures)

        log_profile_event(
            "Phase sync update",
            source=source_name,
            trace=trace_name,
            phase=phase,
            visible=visible,
            state=self.phase_visibility,
        )

        self._sync_phase_visibility_to_webviews(source_name=source_name)

    def _apply_interface_visual_standard(
        self,
        graph_name: str,
        fig: go.Figure,
        dataframe: pd.DataFrame,
        zoom_mode: bool = False,
    ):
        if graph_name == "Consumo":
            return apply_fixed_y_subdivisions(fig)

        fig = apply_default_x_density(fig, dataframe)

        if zoom_mode:
            if graph_name != "Fator de Potência":
                fig = apply_zoom_y_autorange(fig)
            return fig

        if graph_name in FIXED_Y_GRAPHS:
            fig = apply_fixed_y_subdivisions(fig)

        return fig

    def _rebuild_figures_for_range(self, processed: ProcessedData, x_min=None, x_max=None):
        zoom_mode = x_min is not None and x_max is not None

        with profile_block("Graph rebuild", zoom=zoom_mode):
            df = processed.dataframe.copy()
            df["Datetime"] = pd.to_datetime(df["Datetime"])

            if zoom_mode:
                x_min = pd.to_datetime(x_min)
                x_max = pd.to_datetime(x_max)
                df = df[(df["Datetime"] >= x_min) & (df["Datetime"] <= x_max)].copy()

            log_profile_event(
                "Graph rebuild dataframe",
                zoom=zoom_mode,
                rows=len(df),
                columns=len(df.columns),
            )

            filtered_processed = ProcessedData(
                company=processed.company,
                city=processed.city,
                trafo=processed.trafo,
                local=processed.local,
                revision=processed.revision,
                excel_path=processed.excel_path,
                dataframe=df,
                integration_time=processed.integration_time,
                tension=processed.tension,
                equipment_type=processed.equipment_type,
                equipment_reference=processed.equipment_reference,
                equipment_value=processed.equipment_value,
            )

            builders = [
                ("Tensão", create_tension_graph),
                ("Corrente", create_current_graph),
                ("Potência Ativa", create_active_power_graph),
                ("Potência Aparente", create_apparent_power_graph),
                ("Fator de Potência", create_pf_graph),
                ("Deseq. Tensão", create_tension_imbalance_graph),
                ("Deseq. Corrente", create_current_imbalance_graph),
                ("Consumo", create_consumption_graph),
                ("DHT Tensão", create_dht_voltage_graph),
                ("DHT Corrente", create_dht_current_graph),
                ("Tensão x Corrente", create_combined_vxi_graph),
                ("kW x kVA", create_combined_kwxkva_graph),
            ]

            figures = {}

            for name, builder in builders:
                with profile_block("Graph build", graph=name, zoom=zoom_mode, rows=len(df)):
                    fig = builder(filtered_processed, show_logo=False)
                    fig = self._apply_interface_visual_standard(
                        graph_name=name,
                        fig=fig,
                        dataframe=df,
                        zoom_mode=zoom_mode,
                    )
                    apply_phase_visibility_to_figure(
                        fig=fig,
                        graph_name=name,
                        phase_visibility=self.phase_visibility,
                    )
                    update_phase_extreme_traces(fig, name)
                    figures[name] = fig

            return figures, df

    def _on_zoom_changed(self, source_name, x_min_str, x_max_str):
        if self.syncing_zoom:
            return

        if not self.current_processed:
            return

        self.syncing_zoom = True

        try:
            with profile_block("Zoom rebuild total", source=source_name):
                if x_min_str == "__FULL_VIEW__" or x_max_str == "__FULL_VIEW__":
                    self.current_x_min = None
                    self.current_x_max = None

                    figures, df = self._rebuild_figures_for_range(
                        self.current_processed,
                        None,
                        None,
                    )

                    self.current_figures = figures

                    for tab_name, fig in figures.items():
                        self._render_webview_figure(tab_name, fig)

                    return

                x_min = pd.to_datetime(x_min_str)
                x_max = pd.to_datetime(x_max_str)

                self.current_x_min = x_min
                self.current_x_max = x_max

                figures, df = self._rebuild_figures_for_range(
                    self.current_processed,
                    x_min,
                    x_max,
                )

                self.current_figures = figures

                for tab_name, fig in figures.items():
                    self._render_webview_figure(tab_name, fig)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro ao sincronizar zoom",
                f"Ocorreu um erro ao sincronizar os gráficos:\n\n{str(e)}"
            )
        finally:
            self.syncing_zoom = False

    def clear_loaded_data(self):
        self.current_processed = None
        self.current_figures = {}
        self.current_x_min = None
        self.current_x_max = None
        self.phase_visibility = default_phase_visibility()

        for webview in self.webviews.values():
            webview.setHtml(
                "<html><body style='background:#000000;color:#f1f1f1;'></body></html>"
            )

        self.pdf_export_tab.select_default()
        self.tabs.setCurrentIndex(0)

    def load_processed_data(self, processed: ProcessedData):
            self.current_processed = processed
            self.current_x_min = None
            self.current_x_max = None
            self.phase_visibility = default_phase_visibility()

            try:
                with profile_block(
                    "Initial graph generation and render",
                    rows=len(processed.dataframe),
                    columns=len(processed.dataframe.columns),
                ):
                    figures, df = self._rebuild_figures_for_range(processed, None, None)
                    self.current_figures = figures

                    for tab_name, fig in figures.items():
                        self._render_webview_figure(tab_name, fig)

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro ao renderizar gráficos",
                    f"Ocorreu um erro ao montar os gráficos:\n\n{str(e)}"
                )
