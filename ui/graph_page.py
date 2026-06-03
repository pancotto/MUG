from pathlib import Path
import sys
import tempfile

import pandas as pd
import plotly.graph_objects as go

from PySide6.QtCore import QObject, QUrl, Signal, Slot, QThread, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
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
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
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
from core.pdf_exporter import (
    build_daily_pdf_filename,
    export_figures_to_pdf,
    GRAPH_EXPORT_ORDER,
)
from core.time_filter import (
    DetectedDay,
    FIRST_RECORD_LABEL,
    FIRST_RECORD_OF_DAY,
    LAST_RECORD_LABEL,
    LAST_RECORD_OF_DAY,
    TimeFilter,
    apply_time_filter,
    custom_time_filter,
    day_bounds_for_date,
    detect_measurement_days,
    filter_matches_measurement_bounds,
    format_datetime,
    format_duration,
    format_time,
    full_measurement_filter,
    get_measurement_bounds,
    measurement_date_options,
    resolve_time_option,
    same_time_filter,
    selected_day_indexes_for_range,
    time_options_for_integration,
)
from ui.about_dialog import AboutDialog


APP_VERSION_FALLBACK = "1.3.6"


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


def format_app_version(version: str) -> str:
    clean = str(version or "").strip()
    if clean.lower().startswith("v"):
        return f"v{clean[1:]}"
    return f"v{clean}"


DEFAULT_PDF_GRAPHS = {
    "Tensão",
    "Corrente",
    "Potência Ativa",
    "Potência Aparente",
    "Fator de Potência",
    "DHT Tensão",
    "DHT Corrente",
}



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

    @Slot(str, str, str)
    def onZoomChanged(self, source_name, x_min, x_max):
        self.zoomChanged.emit(source_name, x_min, x_max)


class PdfExportWorker(QObject):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, processed, selected_graphs, output_dir, zoom_mode):
        super().__init__()
        self.processed = processed
        self.selected_graphs = selected_graphs
        self.output_dir = output_dir
        self.zoom_mode = zoom_mode

    @Slot()
    def run(self):
        try:
            pdf_path = export_figures_to_pdf(
                processed=self.processed,
                selected_graphs=self.selected_graphs,
                output_dir=self.output_dir,
                zoom_mode=self.zoom_mode,
            )
            self.finished.emit(str(pdf_path))
        except Exception as exc:
            self.error.emit(str(exc))


class DailyPdfExportWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(list, list, bool)

    def __init__(self, original_processed, detected_days, selected_graphs, output_dir):
        super().__init__()
        self.original_processed = original_processed
        self.detected_days = tuple(detected_days)
        self.selected_graphs = selected_graphs
        self.output_dir = Path(output_dir)
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    @Slot()
    def run(self):
        successes: list[str] = []
        failures: list[str] = []
        total = len(self.detected_days)
        canceled = False

        for index, day in enumerate(self.detected_days, start=1):
            if self._cancel_requested:
                canceled = True
                break

            label = day.date.strftime("%d/%m/%Y")
            self.progress.emit(index, total, label)

            try:
                dataframe = apply_time_filter(
                    self.original_processed.dataframe,
                    custom_time_filter(
                        day.start_datetime,
                        day.end_datetime,
                        label=day.label,
                    ),
                )

                if dataframe.empty:
                    raise ValueError("Dia sem registros de medição.")

                processed_for_day = ProcessedData(
                    company=self.original_processed.company,
                    city=self.original_processed.city,
                    trafo=self.original_processed.trafo,
                    local=self.original_processed.local,
                    revision=self.original_processed.revision,
                    excel_path=self.original_processed.excel_path,
                    dataframe=dataframe,
                    integration_time=self.original_processed.integration_time,
                    tension=self.original_processed.tension,
                    equipment_type=self.original_processed.equipment_type,
                    equipment_reference=self.original_processed.equipment_reference,
                    equipment_value=self.original_processed.equipment_value,
                )

                generated_path = export_figures_to_pdf(
                    processed=processed_for_day,
                    selected_graphs=self.selected_graphs,
                    output_dir=self.output_dir,
                    zoom_mode=False,
                )
                target_path = self.output_dir / build_daily_pdf_filename(
                    self.original_processed.company,
                    day.date,
                )
                if target_path.exists():
                    target_path.unlink()
                Path(generated_path).replace(target_path)
                successes.append(str(target_path))
            except Exception as exc:
                failures.append(f"{label}: {exc}")

        self.finished.emit(successes, failures, canceled)


class TimeSelectionTab(QWidget):
    def __init__(self, graph_page):
        super().__init__()
        self.graph_page = graph_page
        self.detected_days: tuple[DetectedDay, ...] = tuple()
        self._updating_controls = False
        self._row_default_brush = QBrush(QColor("#111111"))
        self._row_highlight_brush = QBrush(QColor("#3a3a3a"))
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
            QTableWidget {
                background-color: #111111;
                color: #f1f1f1;
                gridline-color: #333333;
                border: 1px solid #222222;
            }
            QHeaderView::section {
                background-color: #2d6cdf;
                color: #ffffff;
                padding: 6px;
                border: none;
                font-weight: bold;
            }
            QComboBox {
                background-color: #111111;
                color: #f1f1f1;
                border: 1px solid #2d6cdf;
                border-radius: 4px;
                padding: 7px;
                min-height: 26px;
            }
            QPushButton {
                background-color: #2d6cdf;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 11px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1f5fbf;
            }
            QPushButton:disabled {
                background-color: #173f7d;
                color: #d0d0d0;
            }
            QTableWidget::item:selected {
                background-color: #3a3a3a;
                color: #ffffff;
            }
        """)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(14)

        title = QLabel("SELEÇÃO")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        root_layout.addWidget(title)

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(10)
        self.period_summary_label = self._create_summary_card(
            "Período da Medição",
            "Carregue uma medição",
        )
        self.duration_summary_label = self._create_summary_card(
            "Duração",
            "-"
        )
        self.integration_summary_label = self._create_summary_card(
            "Integralização",
            "-"
        )
        summary_layout.addWidget(self.period_summary_label, 2)
        summary_layout.addWidget(self.duration_summary_label, 1)
        summary_layout.addWidget(self.integration_summary_label, 1)
        root_layout.addLayout(summary_layout)

        detected_title = QLabel("SELECIONAR DIA")
        detected_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 6px;")
        root_layout.addWidget(detected_title)

        self.day_combo = QComboBox()
        self.day_combo.currentIndexChanged.connect(self._on_day_selected)
        root_layout.addWidget(self.day_combo)

        self.days_table = QTableWidget(0, 4)
        self.days_table.setHorizontalHeaderLabels(
            ["Data", "Hora Inicial", "Hora Final", "Status"]
        )
        self.days_table.verticalHeader().setVisible(False)
        self.days_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.days_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.days_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.days_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.days_table.setMinimumHeight(170)
        self.days_table.cellClicked.connect(self._on_day_row_clicked)
        self.days_table.cellDoubleClicked.connect(self._on_day_row_double_clicked)
        root_layout.addWidget(self.days_table)

        datetime_layout = QHBoxLayout()
        self.start_date_combo = QComboBox()
        self.start_date_combo.currentIndexChanged.connect(self._on_date_range_changed)
        datetime_layout.addWidget(QLabel("Data Inicial"))
        datetime_layout.addWidget(self.start_date_combo, 1)

        self.start_time_combo = QComboBox()
        datetime_layout.addWidget(QLabel("Hora Inicial"))
        datetime_layout.addWidget(self.start_time_combo, 1)

        self.end_date_combo = QComboBox()
        self.end_date_combo.currentIndexChanged.connect(self._on_date_range_changed)
        datetime_layout.addWidget(QLabel("Data Final"))
        datetime_layout.addWidget(self.end_date_combo, 1)

        self.end_time_combo = QComboBox()
        datetime_layout.addWidget(QLabel("Hora Final"))
        datetime_layout.addWidget(self.end_time_combo, 1)
        root_layout.addLayout(datetime_layout)

        action_layout = QHBoxLayout()
        self.full_measurement_button = QPushButton("MEDIÇÃO COMPLETA")
        self.full_measurement_button.setStyleSheet("""
            QPushButton {
                background-color: #2d7d46;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 11px 16px;
                font-size: 13px;
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
        self.full_measurement_button.clicked.connect(self.prepare_full_measurement_selection)
        action_layout.addWidget(self.full_measurement_button)

        self.apply_button = QPushButton("APLICAR SELEÇÃO")
        self.apply_button.clicked.connect(self.apply_selection)
        action_layout.addWidget(self.apply_button)

        self.clear_button = QPushButton("LIMPAR SELEÇÃO")
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #8b1e1e;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 11px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a32626;
            }
            QPushButton:pressed {
                background-color: #6f1818;
            }
            QPushButton:disabled {
                background-color: #4f1717;
                color: #d0d0d0;
            }
        """)
        self.clear_button.clicked.connect(self.clear_selection)
        action_layout.addWidget(self.clear_button)
        root_layout.addLayout(action_layout)

        self.processing_label = QLabel("Atualizando gráficos...")
        self.processing_label.setVisible(False)
        self.processing_label.setStyleSheet("font-size: 13px; color: #bbbbbb; font-weight: bold;")
        self.processing_bar = QProgressBar()
        self.processing_bar.setRange(0, 0)
        self.processing_bar.setVisible(False)
        root_layout.addWidget(self.processing_label)
        root_layout.addWidget(self.processing_bar)

        self.active_interval_label = QLabel("Intervalo Ativo\nMedição Completa")
        self.active_interval_label.setWordWrap(True)
        self.active_interval_label.setStyleSheet("""
            QLabel {
                background-color: #111111;
                border: 1px solid #2d6cdf;
                border-radius: 8px;
                padding: 9px 12px;
                font-size: 13px;
                font-weight: bold;
            }
        """)
        root_layout.addWidget(self.active_interval_label)

        root_layout.addStretch()
        self.setLayout(root_layout)
        self.set_enabled(False)

    @staticmethod
    def _create_summary_card(title: str, value: str) -> QLabel:
        label = QLabel(f"<b>{title}</b><br>{value}")
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setMinimumHeight(58)
        label.setStyleSheet("""
            QLabel {
                background-color: #111111;
                border: 1px solid #222222;
                border-radius: 8px;
                color: #f1f1f1;
                font-size: 13px;
                padding: 10px;
            }
        """)
        return label

    def set_enabled(self, enabled: bool):
        for widget in [
            self.days_table,
            self.full_measurement_button,
            self.day_combo,
            self.start_date_combo,
            self.start_time_combo,
            self.end_date_combo,
            self.end_time_combo,
            self.apply_button,
            self.clear_button,
        ]:
            widget.setEnabled(enabled)

    def set_processing_state(self, processing: bool):
        self.set_enabled(not processing)
        self.processing_label.setVisible(processing)
        self.processing_bar.setVisible(processing)

    def load_processed_data(self, processed: ProcessedData):
        dataframe = processed.dataframe
        self.detected_days = detect_measurement_days(
            dataframe,
            processed.integration_time,
        )
        start, end = get_measurement_bounds(dataframe)
        dates = measurement_date_options(dataframe)
        times = time_options_for_integration(processed.integration_time)

        self._updating_controls = True
        try:
            self.period_summary_label.setText(
                "<b>Período da Medição</b><br>"
                f"{format_datetime(start)} \u2192 {format_datetime(end)}"
            )
            self.duration_summary_label.setText(
                "<b>Duração</b><br>"
                f"{format_duration(start, end)}"
            )
            self.integration_summary_label.setText(
                "<b>Integralização</b><br>"
                f"{processed.integration_time} segundos"
            )

            self._populate_days_table()
            self.day_combo.clear()
            self.day_combo.addItem("MEDIÇÃO COMPLETA", None)
            for index, day in enumerate(self.detected_days):
                self.day_combo.addItem(day.label, index)

            self._populate_date_combos(dates)
            self._populate_time_combos(times)
            self._set_datetime_controls(start, end)
            self._update_day_range_highlight()
        finally:
            self._updating_controls = False

        self.set_enabled(True)
        self.update_active_interval(self.graph_page.current_time_filter)

    def clear_loaded_data(self):
        self.detected_days = tuple()
        self.days_table.setRowCount(0)
        self.day_combo.clear()
        self.start_date_combo.clear()
        self.start_time_combo.clear()
        self.end_date_combo.clear()
        self.end_time_combo.clear()
        self.period_summary_label.setText(
            "<b>Período da Medição</b><br>Carregue uma medição"
        )
        self.duration_summary_label.setText("<b>Duração</b><br>-")
        self.integration_summary_label.setText("<b>Integralização</b><br>-")
        self.active_interval_label.setText("Intervalo Ativo\nMedição Completa")
        self.set_enabled(False)

    def _populate_days_table(self):
        self.days_table.setRowCount(len(self.detected_days))

        for row, day in enumerate(self.detected_days):
            values = [
                day.label,
                format_time(day.start_datetime),
                format_time(day.end_datetime),
                self._display_status(day.status),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(self._row_default_brush)
                self.days_table.setItem(row, column, item)

    def _populate_date_combos(self, dates: tuple[pd.Timestamp, ...]):
        self.start_date_combo.clear()
        self.end_date_combo.clear()

        for value in dates:
            label = pd.Timestamp(value).strftime("%d/%m/%Y")
            iso_value = pd.Timestamp(value).strftime("%Y-%m-%d")
            self.start_date_combo.addItem(label, iso_value)
            self.end_date_combo.addItem(label, iso_value)

    def _populate_time_combos(self, times: tuple[str, ...]):
        self.start_time_combo.clear()
        self.end_time_combo.clear()

        for combo in [self.start_time_combo, self.end_time_combo]:
            combo.addItem(FIRST_RECORD_LABEL, FIRST_RECORD_OF_DAY)
            combo.addItem(LAST_RECORD_LABEL, LAST_RECORD_OF_DAY)

        for value in times:
            self.start_time_combo.addItem(value, value)
            self.end_time_combo.addItem(value, value)

    def _set_datetime_controls(self, start, end):
        start_timestamp = pd.Timestamp(start)
        end_timestamp = pd.Timestamp(end)

        self._set_combo_value(
            self.start_date_combo,
            pd.Timestamp(start_timestamp).strftime("%Y-%m-%d"),
            pd.Timestamp(start_timestamp).strftime("%d/%m/%Y"),
        )
        self._set_combo_value(
            self.end_date_combo,
            pd.Timestamp(end_timestamp).strftime("%Y-%m-%d"),
            pd.Timestamp(end_timestamp).strftime("%d/%m/%Y"),
        )

        self._set_time_combo_value(self.start_time_combo, start_timestamp)
        self._set_time_combo_value(self.end_time_combo, end_timestamp)
        self._update_day_range_highlight()

    @staticmethod
    def _set_combo_value(combo: QComboBox, data_value: str, display_value: str):
        index = combo.findData(data_value)
        if index < 0:
            combo.addItem(display_value, data_value)
            combo.model().sort(0)
            index = combo.findData(data_value)

        if index >= 0:
            combo.setCurrentIndex(index)

    def _set_time_combo_value(self, combo: QComboBox, timestamp: pd.Timestamp):
        timestamp = pd.Timestamp(timestamp)
        date_value = timestamp.strftime("%Y-%m-%d")

        try:
            day_start, day_end = day_bounds_for_date(self.detected_days, date_value)
            if timestamp == pd.Timestamp(day_start):
                index = combo.findData(FIRST_RECORD_OF_DAY)
                if index >= 0:
                    combo.setCurrentIndex(index)
                    return
            if timestamp == pd.Timestamp(day_end):
                index = combo.findData(LAST_RECORD_OF_DAY)
                if index >= 0:
                    combo.setCurrentIndex(index)
                    return
        except Exception:
            pass

        time_value = timestamp.strftime("%H:%M:%S")
        self._set_combo_value(combo, time_value, time_value)

    def _on_day_selected(self, index: int):
        if self._updating_controls:
            return

        if index <= 0:
            self.prepare_full_measurement_selection()
            return

        day_index = self.day_combo.currentData()
        if day_index is None:
            return

        self._select_day(int(day_index))

    def _on_date_range_changed(self, index: int):
        if self._updating_controls:
            return

        self._update_day_range_highlight()

    def _on_day_row_clicked(self, row: int, column: int):
        self._select_day(row)

    def _on_day_row_double_clicked(self, row: int, column: int):
        self._select_day(row)
        self.apply_selection()

    def _select_day(self, day_index: int):
        if day_index < 0 or day_index >= len(self.detected_days):
            return

        selected_day = self.detected_days[day_index]
        self._set_datetime_controls(
            selected_day.start_datetime,
            selected_day.end_datetime,
        )

        self.days_table.selectRow(day_index)
        self._update_day_range_highlight()

        combo_index = self.day_combo.findData(day_index)
        if combo_index >= 0 and self.day_combo.currentIndex() != combo_index:
            self._updating_controls = True
            try:
                self.day_combo.setCurrentIndex(combo_index)
            finally:
                self._updating_controls = False

    def apply_selection(self):
        try:
            start_date = self.start_date_combo.currentData()
            start_time = self.start_time_combo.currentData()
            end_date = self.end_date_combo.currentData()
            end_time = self.end_time_combo.currentData()
            if not start_date or not start_time or not end_date or not end_time:
                raise ValueError("Selecione data e hora inicial/final válidas.")

            start = resolve_time_option(self.detected_days, start_date, start_time)
            end = resolve_time_option(self.detected_days, end_date, end_time)
            selected_filter = custom_time_filter(start, end)

            if (
                self.graph_page.original_dataframe is not None
                and filter_matches_measurement_bounds(
                    self.graph_page.original_dataframe,
                    selected_filter,
                )
            ):
                selected_filter = full_measurement_filter(
                    self.graph_page.original_dataframe
                )

            self.graph_page.apply_time_filter(selected_filter)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Seleção inválida",
                f"Não foi possível aplicar o intervalo selecionado:\n\n{exc}"
            )

    def clear_selection(self):
        self.graph_page.clear_time_filter()

    def prepare_full_measurement_selection(self):
        if self.graph_page.original_dataframe is None:
            return

        start, end = get_measurement_bounds(self.graph_page.original_dataframe)

        self._updating_controls = True
        try:
            self.day_combo.setCurrentIndex(0)
            self._set_datetime_controls(start, end)
        finally:
            self._updating_controls = False
            self.days_table.clearSelection()
            self._update_day_range_highlight()

    def _update_day_range_highlight(self):
        start_date = self.start_date_combo.currentData()
        end_date = self.end_date_combo.currentData()
        highlighted_rows = set(
            selected_day_indexes_for_range(
                self.detected_days,
                start_date,
                end_date,
            )
        )

        for row in range(self.days_table.rowCount()):
            brush = (
                self._row_highlight_brush
                if row in highlighted_rows
                else self._row_default_brush
            )
            for column in range(self.days_table.columnCount()):
                item = self.days_table.item(row, column)
                if item is not None:
                    item.setBackground(brush)

    def update_active_interval(self, time_filter: TimeFilter | None):
        if time_filter is None or time_filter.is_full_measurement:
            if self.graph_page.original_dataframe is not None:
                try:
                    start, end = get_measurement_bounds(
                        self.graph_page.original_dataframe
                    )
                    self._set_datetime_controls(start, end)
                except Exception:
                    pass
            self.active_interval_label.setText(
                "Intervalo Ativo\n"
                "Medição Completa\n"
                f"{format_datetime(start)} \u2192 {format_datetime(end)}"
            )
            return

        start = pd.Timestamp(time_filter.start_datetime)
        end = pd.Timestamp(time_filter.end_datetime)
        self.active_interval_label.setText(
            "Intervalo Ativo\n"
            f"{format_datetime(start)} \u2192 {format_datetime(end)}\n"
            f"Duração: {format_duration(start, end)}"
        )

    @staticmethod
    def _display_status(status: str) -> str:
        return {
            "Complete": "Completo",
            "Incomplete": "Incompleto",
        }.get(status, status)

class PdfExportTab(QWidget):
    def __init__(self, graph_page):
        super().__init__()
        self.graph_page = graph_page
        self.checkboxes: dict[str, QCheckBox] = {}
        self.default_pdf_graphs = DEFAULT_PDF_GRAPHS
        self._pdf_thread: QThread | None = None
        self._pdf_worker: PdfExportWorker | None = None
        self._daily_pdf_thread: QThread | None = None
        self._daily_pdf_worker: DailyPdfExportWorker | None = None
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

        self.export_daily_button = QPushButton("EXPORTAR MEDIÇÃO COMPLETA COM PDFs DIÁRIOS")
        self.export_daily_button.setStyleSheet("""
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
        self.export_daily_button.clicked.connect(self.export_daily_pdfs)

        self.cancel_daily_button = QPushButton("PARAR EXPORTAÇÃO")
        self.cancel_daily_button.setVisible(False)
        self.cancel_daily_button.setStyleSheet("""
            QPushButton {
                background-color: #8b1e1e;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 18px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a32626;
            }
            QPushButton:pressed {
                background-color: #6f1818;
            }
            QPushButton:disabled {
                background-color: #4f1717;
                color: #d0d0d0;
            }
        """)
        self.cancel_daily_button.clicked.connect(self.cancel_daily_export)

        buttons_layout = QVBoxLayout()
        buttons_layout.addWidget(self.select_default_button)
        buttons_layout.addWidget(self.select_all_button)
        buttons_layout.addWidget(self.clear_all_button)
        buttons_layout.addWidget(self.export_button)
        buttons_layout.addWidget(self.export_daily_button)
        buttons_layout.addWidget(self.cancel_daily_button)
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
        self.export_daily_button.setDisabled(exporting)
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
            self.export_daily_button.setText("EXPORTAR MEDIÇÃO COMPLETA COM PDFs DIÁRIOS")
            self.cancel_daily_button.setVisible(False)
            self.cancel_daily_button.setEnabled(False)
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

    def _selected_graphs(self) -> list[str]:
        return [
            name for name, checkbox in self.checkboxes.items()
            if checkbox.isChecked()
        ]

    def _validate_pdf_preflight(
        self,
        selected_graphs: list[str],
        output_dir: Path | None = None,
        require_detected_days: bool = False,
    ) -> bool:
        if not selected_graphs:
            QMessageBox.warning(
                self,
                "Exportar PDF",
                "Selecione pelo menos um gráfico para exportação."
            )
            return False

        if not self.graph_page.current_processed:
            QMessageBox.warning(
                self,
                "Exportar PDF",
                "Nenhum gráfico foi carregado ainda."
            )
            return False

        if require_detected_days and not self.graph_page.time_selection_tab.detected_days:
            QMessageBox.warning(
                self,
                "Exportar PDF diários",
                "Nenhum dia de medição foi detectado para exportação diária."
            )
            return False

        if output_dir is not None:
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                test_file = output_dir / ".mug_write_test"
                test_file.write_text("ok", encoding="utf-8")
                test_file.unlink(missing_ok=True)
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Exportar PDF",
                    f"A pasta de destino não está disponível para gravação:\n\n{exc}"
                )
                return False

        try:
            with tempfile.TemporaryDirectory(prefix="mug_pdf_preflight_"):
                pass
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Exportar PDF",
                f"Não foi possível usar a pasta temporária do sistema:\n\n{exc}"
            )
            return False

        return True

    def export_pdf(self):
        selected_graphs = self._selected_graphs()

        if not self._validate_pdf_preflight(selected_graphs):
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de destino do PDF"
        )

        if not output_dir:
            return

        try:
            output_path = Path(output_dir)
            if not self._validate_pdf_preflight(selected_graphs, output_path):
                return

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

    def export_daily_pdfs(self):
        selected_graphs = self._selected_graphs()

        if not self._validate_pdf_preflight(
            selected_graphs,
            require_detected_days=True,
        ):
            return

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de destino dos PDFs diários"
        )

        if not output_dir:
            return

        output_path = Path(output_dir)
        if not self._validate_pdf_preflight(
            selected_graphs,
            output_path,
            require_detected_days=True,
        ):
            return

        if self.graph_page.original_processed is None:
            QMessageBox.warning(
                self,
                "Exportar PDF diários",
                "Nenhuma medição original está disponível para exportação diária."
            )
            return

        self.set_exporting_state(True)
        self.export_button.setText("EXPORTANDO PDF...")
        self.export_daily_button.setText("EXPORTANDO PDFs DIÁRIOS...")
        self.cancel_daily_button.setVisible(True)
        self.cancel_daily_button.setEnabled(True)
        self.status_label.setText("Preparando exportação diária. Aguarde...")

        self._daily_pdf_thread = QThread()
        self._daily_pdf_worker = DailyPdfExportWorker(
            original_processed=self.graph_page.original_processed,
            detected_days=self.graph_page.time_selection_tab.detected_days,
            selected_graphs=selected_graphs,
            output_dir=output_path,
        )
        self._daily_pdf_worker.moveToThread(self._daily_pdf_thread)

        self._daily_pdf_thread.started.connect(self._daily_pdf_worker.run)
        self._daily_pdf_worker.progress.connect(self._on_daily_pdf_progress)
        self._daily_pdf_worker.finished.connect(self._on_daily_pdf_finished)
        self._daily_pdf_worker.finished.connect(self._daily_pdf_thread.quit)
        self._daily_pdf_thread.finished.connect(self._daily_pdf_worker.deleteLater)
        self._daily_pdf_thread.finished.connect(self._daily_pdf_thread.deleteLater)
        self._daily_pdf_thread.finished.connect(self._clear_daily_pdf_thread_refs)
        self._daily_pdf_thread.start()

    def cancel_daily_export(self):
        if self._daily_pdf_worker is None:
            return

        self._daily_pdf_worker.request_cancel()
        self.cancel_daily_button.setEnabled(False)
        self.status_label.setText("Cancelando exportação...")

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

    def _on_daily_pdf_progress(self, current: int, total: int, day_label: str):
        self.status_label.setText(
            f"Exportando PDF diário {current} de {total}...\n{day_label}"
        )

    def _on_daily_pdf_finished(self, successes: list, failures: list, canceled: bool):
        self.set_exporting_state(False)

        if canceled:
            QMessageBox.information(
                self,
                "Exportação cancelada",
                "Exportação cancelada pelo usuário.\n"
                f"PDFs gerados até o cancelamento: {len(successes)} de "
                f"{len(self.graph_page.time_selection_tab.detected_days)}."
            )
            return

        if failures:
            QMessageBox.warning(
                self,
                "Exportação diária concluída com avisos",
                "PDFs gerados com sucesso: "
                f"{len(successes)}\n\nFalhas:\n" + "\n".join(str(item) for item in failures)
            )
            return

        QMessageBox.information(
            self,
            "PDFs diários gerados",
            f"{len(successes)} PDF(s) diário(s) gerado(s) com sucesso."
        )

    def _clear_daily_pdf_thread_refs(self):
        self._daily_pdf_thread = None
        self._daily_pdf_worker = None

class GraphPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.original_processed: ProcessedData | None = None
        self.original_dataframe: pd.DataFrame | None = None
        self.current_processed: ProcessedData | None = None
        self.current_figures: dict[str, go.Figure] = {}
        self.webviews: dict[str, QWebEngineView] = {}
        self.current_time_filter: TimeFilter | None = None

        self.syncing_zoom = False
        self.current_x_min = None
        self.current_x_max = None

        self.plot_bridge = PlotBridge()
        self.plot_bridge.zoomChanged.connect(self._on_zoom_changed)

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

        self.time_selection_tab = TimeSelectionTab(self)
        self.selection_tab_index = self.tabs.addTab(
            self.time_selection_tab,
            "SELEÇÃO"
        )

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
            format_app_version(get_app_version())
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
            app_version=format_app_version(get_app_version()),
            available_update=getattr(
                self.main_window,
                "available_update",
                None
            )
        )

        dialog.exec()


    def _build_html_with_zoom_sync(self, fig: go.Figure, source_name: str):
            html = fig.to_html(full_html=True, include_plotlyjs=True, div_id="plot")

            extra_js = f"""
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script>
            (function() {{
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
        df = processed.dataframe.copy()
        df["Datetime"] = pd.to_datetime(df["Datetime"])

        zoom_mode = x_min is not None and x_max is not None

        if zoom_mode:
            x_min = pd.to_datetime(x_min)
            x_max = pd.to_datetime(x_max)
            df = df[(df["Datetime"] >= x_min) & (df["Datetime"] <= x_max)].copy()

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

        figures = {
            "Tensão": create_tension_graph(filtered_processed, show_logo=False),
            "Corrente": create_current_graph(filtered_processed, show_logo=False),
            "Potência Ativa": create_active_power_graph(filtered_processed, show_logo=False),
            "Potência Aparente": create_apparent_power_graph(filtered_processed, show_logo=False),
            "Fator de Potência": create_pf_graph(filtered_processed, show_logo=False),
            "Deseq. Tensão": create_tension_imbalance_graph(filtered_processed, show_logo=False),
            "Deseq. Corrente": create_current_imbalance_graph(filtered_processed, show_logo=False),
            "Consumo": create_consumption_graph(filtered_processed, show_logo=False),
            "DHT Tensão": create_dht_voltage_graph(filtered_processed, show_logo=False),
            "DHT Corrente": create_dht_current_graph(filtered_processed, show_logo=False),
            "Tensão x Corrente": create_combined_vxi_graph(filtered_processed, show_logo=False),
            "kW x kVA": create_combined_kwxkva_graph(filtered_processed, show_logo=False),
        }

        for name, fig in figures.items():
            figures[name] = self._apply_interface_visual_standard(
                graph_name=name,
                fig=fig,
                dataframe=df,
                zoom_mode=zoom_mode,
            )

        return figures, df

    def _build_processed_with_dataframe(self, dataframe: pd.DataFrame) -> ProcessedData:
        if self.original_processed is None:
            raise ValueError("Nenhuma medição original está carregada.")

        return ProcessedData(
            company=self.original_processed.company,
            city=self.original_processed.city,
            trafo=self.original_processed.trafo,
            local=self.original_processed.local,
            revision=self.original_processed.revision,
            excel_path=self.original_processed.excel_path,
            dataframe=dataframe,
            integration_time=self.original_processed.integration_time,
            tension=self.original_processed.tension,
            equipment_type=self.original_processed.equipment_type,
            equipment_reference=self.original_processed.equipment_reference,
            equipment_value=self.original_processed.equipment_value,
        )

    def _refresh_graphs_for_current_processed(self):
        if self.current_processed is None:
            return

        figures, df = self._rebuild_figures_for_range(
            self.current_processed,
            None,
            None,
        )
        self.current_figures = figures

        for tab_name, fig in figures.items():
            self._render_webview_figure(tab_name, fig)

    def apply_time_filter(self, time_filter: TimeFilter):
        if self.original_dataframe is None or self.original_processed is None:
            return

        if same_time_filter(self.current_time_filter, time_filter):
            return

        self.time_selection_tab.set_processing_state(True)
        QApplication.processEvents()

        try:
            filtered_dataframe = apply_time_filter(
                self.original_dataframe,
                time_filter,
            )

            if filtered_dataframe.empty:
                QMessageBox.warning(
                    self,
                    "Seleção sem dados",
                    "O intervalo selecionado não possui registros de medição."
                )
                return

            self.current_time_filter = time_filter
            self.current_processed = self._build_processed_with_dataframe(
                filtered_dataframe
            )
            self.current_x_min = None
            self.current_x_max = None
            self._refresh_graphs_for_current_processed()
            self._update_filter_indicator()
            self.time_selection_tab.update_active_interval(self.current_time_filter)
        finally:
            self.time_selection_tab.set_processing_state(False)

    def clear_time_filter(self):
        if self.original_dataframe is None:
            return

        if (
            self.current_time_filter is not None
            and self.current_time_filter.is_full_measurement
        ):
            return

        self.apply_time_filter(
            full_measurement_filter(self.original_dataframe)
        )

    def _update_filter_indicator(self):
        return None

    def _on_zoom_changed(self, source_name, x_min_str, x_max_str):
        if self.syncing_zoom:
            return

        if not self.current_processed:
            return

        self.syncing_zoom = True

        try:
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
        self.original_processed = None
        self.original_dataframe = None
        self.current_processed = None
        self.current_figures = {}
        self.current_time_filter = None
        self.current_x_min = None
        self.current_x_max = None

        for webview in self.webviews.values():
            webview.setHtml(
                "<html><body style='background:#000000;color:#f1f1f1;'></body></html>"
            )

        self.time_selection_tab.clear_loaded_data()
        self._update_filter_indicator()
        self.pdf_export_tab.select_default()
        self.tabs.setCurrentIndex(0)

    def load_processed_data(self, processed: ProcessedData):
            original_dataframe = processed.dataframe.copy(deep=True)
            self.original_dataframe = original_dataframe
            self.original_processed = ProcessedData(
                company=processed.company,
                city=processed.city,
                trafo=processed.trafo,
                local=processed.local,
                revision=processed.revision,
                excel_path=processed.excel_path,
                dataframe=original_dataframe,
                integration_time=processed.integration_time,
                tension=processed.tension,
                equipment_type=processed.equipment_type,
                equipment_reference=processed.equipment_reference,
                equipment_value=processed.equipment_value,
            )
            self.current_time_filter = full_measurement_filter(original_dataframe)
            self.current_processed = self._build_processed_with_dataframe(
                apply_time_filter(original_dataframe, self.current_time_filter)
            )
            self.current_x_min = None
            self.current_x_max = None

            try:
                self.time_selection_tab.load_processed_data(self.original_processed)
                self._update_filter_indicator()

                figures, df = self._rebuild_figures_for_range(
                    self.current_processed,
                    None,
                    None,
                )
                self.current_figures = figures

                for tab_name, fig in figures.items():
                    self._render_webview_figure(tab_name, fig)

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro ao renderizar gráficos",
                    f"Ocorreu um erro ao montar os gráficos:\n\n{str(e)}"
                )
