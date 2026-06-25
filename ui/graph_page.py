from pathlib import Path
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

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
    QFrame,
    QGridLayout,
    QGroupBox,
    QMessageBox,
    QLabel,
    QPushButton,
    QCheckBox,
    QRadioButton,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
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
from core.models import ProcessedData, format_numeric_value
from core.pdf_exporter import (
    build_custom_pdf_filename,
    build_daily_pdf_filename,
    ensure_unique_pdf_path,
    export_figures_to_pdf,
    GRAPH_EXPORT_ORDER,
    next_pdf_suffix_path,
    reserve_unique_pdf_paths,
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
from ui.input_validation import (
    enable_uppercase_input,
    set_decimal_number_validator,
    set_digits_only_validator,
)


APP_VERSION_FALLBACK = "1.4.0"
CUSTOM_DAILY_PDF_MAX_WORKERS = 2


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
    canceled = Signal()

    def __init__(self, processed, selected_graphs, output_dir, zoom_mode, pdf_filename=None):
        super().__init__()
        self.processed = processed
        self.selected_graphs = selected_graphs
        self.output_dir = output_dir
        self.zoom_mode = zoom_mode
        self.pdf_filename = pdf_filename
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    @Slot()
    def run(self):
        try:
            if self._cancel_requested:
                self.canceled.emit()
                return

            pdf_path = export_figures_to_pdf(
                processed=self.processed,
                selected_graphs=self.selected_graphs,
                output_dir=self.output_dir,
                zoom_mode=self.zoom_mode,
                pdf_filename=self.pdf_filename,
            )
            if self._cancel_requested:
                self.canceled.emit()
                return

            self.finished.emit(str(pdf_path))
        except Exception as exc:
            self.error.emit(str(exc))


class CustomPdfExportWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(list, list, bool)

    def __init__(self, export_tasks, selected_graphs, output_dir):
        super().__init__()
        self.export_tasks = tuple(export_tasks)
        self.selected_graphs = selected_graphs
        self.output_dir = Path(output_dir)
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    def _export_task(self, task):
        with tempfile.TemporaryDirectory(prefix="mug_pdf_export_") as temp_dir:
            generated_path = Path(export_figures_to_pdf(
                processed=task["processed"],
                selected_graphs=self.selected_graphs,
                output_dir=Path(temp_dir),
                zoom_mode=False,
                pdf_filename=task["filename"],
            ))

            target_path = Path(task["output_path"])
            target_path.parent.mkdir(parents=True, exist_ok=True)

            for _ in range(25):
                safe_target = ensure_unique_pdf_path(target_path)
                try:
                    generated_path.replace(safe_target)
                    return str(safe_target)
                except PermissionError:
                    target_path = next_pdf_suffix_path(safe_target)

            raise PermissionError(
                f"Não foi possível gravar o PDF em um nome livre: {task['output_path']}"
            )

    @Slot()
    def run(self):
        successes: list[str] = []
        failures: list[str] = []
        total = len(self.export_tasks)
        canceled = False

        if total > 1:
            with ThreadPoolExecutor(max_workers=CUSTOM_DAILY_PDF_MAX_WORKERS) as executor:
                for index in range(0, total, CUSTOM_DAILY_PDF_MAX_WORKERS):
                    if self._cancel_requested:
                        canceled = True
                        break

                    batch = self.export_tasks[index:index + CUSTOM_DAILY_PDF_MAX_WORKERS]
                    futures = [
                        (task, executor.submit(self._export_task, task))
                        for task in batch
                    ]

                    for offset, (task, future) in enumerate(futures, start=1):
                        current = index + offset
                        label = task["label"]
                        self.progress.emit(current, total, label)
                        try:
                            successes.append(future.result())
                        except Exception as exc:
                            failures.append(f"{label}: {exc}")

                    if self._cancel_requested:
                        canceled = True
                        break

            self.finished.emit(successes, failures, canceled)
            return

        for index, task in enumerate(self.export_tasks, start=1):
            if self._cancel_requested:
                canceled = True
                break

            label = task["label"]
            self.progress.emit(index, total, label)

            try:
                successes.append(self._export_task(task))
            except Exception as exc:
                failures.append(f"{label}: {exc}")

        self.finished.emit(successes, failures, canceled)


class DetectedDaysTable(QTableWidget):
    dragRangeChanged = Signal(int, int)
    shiftRangeSelected = Signal(int, int)

    def __init__(self, rows: int, columns: int, parent=None):
        super().__init__(rows, columns, parent)
        self._drag_start_row: int | None = None
        self._drag_moved = False
        self._anchor_row: int | None = None
        self._shift_range_active = False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            row = self.rowAt(event.position().toPoint().y())
            if row >= 0:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    anchor = self._anchor_row if self._anchor_row is not None else row
                    self.shiftRangeSelected.emit(anchor, row)
                    if self._anchor_row is None:
                        self._anchor_row = row
                    self._drag_start_row = None
                    self._drag_moved = False
                    self._shift_range_active = True
                    super().mousePressEvent(event)
                    return

                self._drag_start_row = row
                self._drag_moved = False
                self._anchor_row = row
                self._shift_range_active = False
                self.dragRangeChanged.emit(row, row)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_start_row is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            row = self.rowAt(event.position().toPoint().y())
            if row >= 0:
                if row != self._drag_start_row:
                    self._drag_moved = True
                self.dragRangeChanged.emit(self._drag_start_row, row)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._shift_range_active:
            self.blockSignals(True)
            try:
                super().mouseReleaseEvent(event)
            finally:
                self.blockSignals(False)
                self._shift_range_active = False
            return

        if event.button() == Qt.MouseButton.LeftButton and self._drag_moved:
            self.blockSignals(True)
            try:
                super().mouseReleaseEvent(event)
            finally:
                self.blockSignals(False)
        else:
            super().mouseReleaseEvent(event)

        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_row = None
            self._drag_moved = False


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

        self.days_table = DetectedDaysTable(0, 4)
        self.days_table.setHorizontalHeaderLabels(
            ["Data", "Hora Inicial", "Hora Final", "Status"]
        )
        self.days_table.verticalHeader().setVisible(False)
        self.days_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.days_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.days_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.days_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.days_table.setMinimumHeight(170)
        self.days_table.dragRangeChanged.connect(self._on_day_drag_range_changed)
        self.days_table.shiftRangeSelected.connect(self._on_day_drag_range_changed)
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

    @staticmethod
    def _set_combo_by_data(combo: QComboBox, data_value: str):
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

    def _on_day_drag_range_changed(self, start_row: int, end_row: int):
        self._select_day_range(start_row, end_row)

    def _select_day_range(self, start_row: int, end_row: int):
        if not self.detected_days:
            return

        first_row = max(0, min(start_row, end_row))
        last_row = min(len(self.detected_days) - 1, max(start_row, end_row))
        if first_row > last_row:
            return

        start_day = self.detected_days[first_row]
        end_day = self.detected_days[last_row]

        self._updating_controls = True
        try:
            self._set_combo_value(
                self.start_date_combo,
                pd.Timestamp(start_day.date).strftime("%Y-%m-%d"),
                pd.Timestamp(start_day.date).strftime("%d/%m/%Y"),
            )
            self._set_combo_value(
                self.end_date_combo,
                pd.Timestamp(end_day.date).strftime("%Y-%m-%d"),
                pd.Timestamp(end_day.date).strftime("%d/%m/%Y"),
            )
            self._set_combo_by_data(self.start_time_combo, FIRST_RECORD_OF_DAY)
            self._set_combo_by_data(self.end_time_combo, LAST_RECORD_OF_DAY)
        finally:
            self._updating_controls = False

        if first_row == last_row:
            combo_index = self.day_combo.findData(first_row)
            if combo_index >= 0 and self.day_combo.currentIndex() != combo_index:
                self._updating_controls = True
                try:
                    self.day_combo.setCurrentIndex(combo_index)
                finally:
                    self._updating_controls = False

        self.days_table.clearSelection()
        self._update_day_range_highlight()

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


class CustomMeasurementExportPanel(QWidget):
    def __init__(
        self,
        parent,
        original_processed: ProcessedData | None = None,
        detected_days: tuple[DetectedDay, ...] = (),
        selected_graphs: list[str] | None = None,
    ):
        super().__init__(parent)
        self.original_processed = original_processed
        self.detected_days = tuple(detected_days)
        self.initial_selected_graphs = set(selected_graphs or [])
        self.graph_checkboxes: dict[str, QCheckBox] = {}
        self.day_checkboxes: list[QCheckBox] = []
        self._graph_column_count = 0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._build_ui()
        self._update_visibility()

    def _build_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                color: #f1f1f1;
                font-family: Arial;
            }
            QGroupBox {
                color: #f1f1f1;
                border: 1px solid #333333;
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel, QRadioButton, QCheckBox {
                color: #f1f1f1;
                background-color: transparent;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border-radius: 7px;
                border: 1px solid #777777;
                background-color: #111111;
            }
            QRadioButton::indicator:checked {
                border: 1px solid #2d6cdf;
                background-color: #2d6cdf;
            }
            QComboBox {
                background-color: #111111;
                color: #f1f1f1;
                border: 1px solid #2d6cdf;
                border-radius: 4px;
                padding: 6px;
                min-height: 24px;
            }
            QPushButton {
                background-color: #1f5fbf;
                color: #ffffff;
                border: none;
                border-radius: 7px;
                padding: 9px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #194f9e;
            }
        """)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(8)

        title = QLabel("EXPORTAR MEDIÇÃO PERSONALIZADA")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root_layout.addWidget(title)

        root_layout.addWidget(self._build_scope_group())
        root_layout.addWidget(self._build_mode_group())
        root_layout.addWidget(self._build_graph_group())

        self.setLayout(root_layout)

    def refresh_context(
        self,
        original_processed: ProcessedData | None,
        detected_days: tuple[DetectedDay, ...],
    ):
        self.original_processed = original_processed
        self.detected_days = tuple(detected_days)
        self._populate_interval_controls()
        self._update_visibility()

    def _build_scope_group(self) -> QGroupBox:
        group = QGroupBox("1. Intervalo Personalizado")
        layout = QVBoxLayout()

        self.day_combo = QComboBox()
        self.day_combo.currentIndexChanged.connect(self._on_day_selected)
        layout.addWidget(self.day_combo)

        self.days_table = DetectedDaysTable(0, 4)
        self.days_table.setHorizontalHeaderLabels(
            ["Data", "Hora Inicial", "Hora Final", "Status"]
        )
        self.days_table.verticalHeader().setVisible(False)
        self.days_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.days_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.days_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.days_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.days_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.days_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.days_table.setMinimumHeight(145)
        self.days_table.setMaximumHeight(175)
        self.days_table.dragRangeChanged.connect(self._on_day_drag_range_changed)
        self.days_table.shiftRangeSelected.connect(self._on_day_drag_range_changed)
        self.days_table.cellClicked.connect(self._on_day_row_clicked)
        self.days_table.cellDoubleClicked.connect(self._on_day_row_clicked)
        layout.addWidget(self.days_table)

        self._row_default_brush = QBrush(QColor("#111111"))
        self._row_highlight_brush = QBrush(QColor("#3a3a3a"))

        interval_layout = QGridLayout()
        interval_layout.setContentsMargins(0, 6, 0, 6)
        interval_layout.setHorizontalSpacing(8)
        interval_layout.setVerticalSpacing(4)
        self.start_date_combo = QComboBox()
        self.start_date_combo.currentIndexChanged.connect(self._on_date_range_changed)
        self.start_time_combo = QComboBox()
        self.end_date_combo = QComboBox()
        self.end_date_combo.currentIndexChanged.connect(self._on_date_range_changed)
        self.end_time_combo = QComboBox()
        for combo in [
            self.start_date_combo,
            self.start_time_combo,
            self.end_date_combo,
            self.end_time_combo,
        ]:
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        interval_fields = [
            ("Data Inicial", self.start_date_combo),
            ("Hora Inicial", self.start_time_combo),
            ("Data Final", self.end_date_combo),
            ("Hora Final", self.end_time_combo),
        ]
        for index, (label, combo) in enumerate(interval_fields):
            interval_layout.addWidget(QLabel(label), 0, index)
            interval_layout.addWidget(combo, 1, index)
        layout.addLayout(interval_layout)

        self._populate_interval_controls()

        group.setLayout(layout)
        return group

    def _build_mode_group(self) -> QGroupBox:
        group = QGroupBox("2. Modo de Exportação")
        layout = QHBoxLayout()
        self.mode_single_radio = QRadioButton("PDF ÚNICO")
        self.mode_daily_radio = QRadioButton("PDFs SEPARADOS POR DIA")
        self.mode_single_radio.setChecked(True)
        layout.addWidget(self.mode_single_radio)
        layout.addWidget(self.mode_daily_radio)
        group.setLayout(layout)
        return group

    def _build_graph_group(self) -> QGroupBox:
        group = QGroupBox("3. Gráficos")
        layout = QVBoxLayout()

        quick_layout = QGridLayout()
        quick_layout.setHorizontalSpacing(8)
        quick_layout.setVerticalSpacing(6)
        for label, callback, is_clear in [
            ("SELEÇÃO PADRÃO", self._select_default_graphs, False),
            ("SELECIONAR TODOS", self._select_all_graphs, False),
            ("LIMPAR SELEÇÃO", self._clear_graphs, True),
        ]:
            button = QPushButton(label)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if is_clear:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #8b1e1e;
                        color: #ffffff;
                        border: none;
                        border-radius: 7px;
                        padding: 9px 14px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #a32626;
                    }
                    QPushButton:pressed {
                        background-color: #6f1818;
                    }
                """)
            else:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #2d7d46;
                        color: #ffffff;
                        border: none;
                        border-radius: 7px;
                        padding: 9px 14px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #25673a;
                    }
                    QPushButton:pressed {
                        background-color: #1f5131;
                    }
                """)
            button.clicked.connect(callback)
            quick_layout.addWidget(button, 0, quick_layout.count())
        layout.addLayout(quick_layout)

        self.graph_grid_layout = QGridLayout()
        self.graph_grid_layout.setHorizontalSpacing(18)
        self.graph_grid_layout.setVerticalSpacing(8)
        for graph_name in GRAPH_EXPORT_ORDER:
            checkbox = QCheckBox(graph_name)
            checkbox.setChecked(graph_name in self.initial_selected_graphs)
            self.graph_checkboxes[graph_name] = checkbox
        self._arrange_graph_checkboxes(3)
        layout.addLayout(self.graph_grid_layout)
        group.setLayout(layout)
        return group

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange_graph_checkboxes(3 if self.width() >= 860 else 2)

    def _arrange_graph_checkboxes(self, column_count: int):
        if self._graph_column_count == column_count:
            return

        while self.graph_grid_layout.count():
            self.graph_grid_layout.takeAt(0)

        self._graph_column_count = column_count
        for index, graph_name in enumerate(GRAPH_EXPORT_ORDER):
            checkbox = self.graph_checkboxes[graph_name]
            row = index // column_count
            column = index % column_count
            self.graph_grid_layout.addWidget(checkbox, row, column)

    def _populate_interval_controls(self):
        self.day_combo.blockSignals(True)
        self.start_date_combo.blockSignals(True)
        self.end_date_combo.blockSignals(True)
        self.start_date_combo.clear()
        self.start_time_combo.clear()
        self.end_date_combo.clear()
        self.end_time_combo.clear()
        self.day_combo.clear()
        self.days_table.setRowCount(0)

        if self.original_processed is None:
            self.day_combo.blockSignals(False)
            self.start_date_combo.blockSignals(False)
            self.end_date_combo.blockSignals(False)
            return

        dataframe = self.original_processed.dataframe
        dates = measurement_date_options(dataframe)
        times = time_options_for_integration(self.original_processed.integration_time)

        self.day_combo.addItem("MEDIÇÃO COMPLETA", None)
        for index, day in enumerate(self.detected_days):
            self.day_combo.addItem(day.label, index)

        self._populate_days_table()

        for date_value in dates:
            label = pd.Timestamp(date_value).strftime("%d/%m/%Y")
            iso_value = pd.Timestamp(date_value).strftime("%Y-%m-%d")
            self.start_date_combo.addItem(label, iso_value)
            self.end_date_combo.addItem(label, iso_value)
        for combo in [self.start_time_combo, self.end_time_combo]:
            combo.addItem(FIRST_RECORD_LABEL, FIRST_RECORD_OF_DAY)
            combo.addItem(LAST_RECORD_LABEL, LAST_RECORD_OF_DAY)
            for time_value in times:
                combo.addItem(time_value, time_value)
        try:
            start, end = get_measurement_bounds(dataframe)
            self._set_combo_value(self.start_date_combo, start.strftime("%Y-%m-%d"))
            self._set_combo_value(self.end_date_combo, end.strftime("%Y-%m-%d"))
            self._set_combo_value(self.start_time_combo, FIRST_RECORD_OF_DAY)
            self._set_combo_value(self.end_time_combo, LAST_RECORD_OF_DAY)
        except Exception:
            pass

        self.day_combo.blockSignals(False)
        self.start_date_combo.blockSignals(False)
        self.end_date_combo.blockSignals(False)
        self._update_day_range_highlight()

    def _populate_days_table(self):
        self.days_table.setRowCount(len(self.detected_days))
        for row, day in enumerate(self.detected_days):
            values = [
                day.label,
                format_time(day.start_datetime),
                format_time(day.end_datetime),
                TimeSelectionTab._display_status(day.status),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(self._row_default_brush)
                self.days_table.setItem(row, column, item)

    @staticmethod
    def _set_combo_value(combo: QComboBox, data_value: str):
        index = combo.findData(data_value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _update_visibility(self, *args):
        self._update_day_range_highlight()

    def _selected_graphs(self) -> list[str]:
        return [
            name for name, checkbox in self.graph_checkboxes.items()
            if checkbox.isChecked()
        ]

    def _select_default_graphs(self):
        for graph_name, checkbox in self.graph_checkboxes.items():
            checkbox.setChecked(graph_name in DEFAULT_PDF_GRAPHS)

    def _select_all_graphs(self):
        for checkbox in self.graph_checkboxes.values():
            checkbox.setChecked(True)

    def _clear_graphs(self):
        for checkbox in self.graph_checkboxes.values():
            checkbox.setChecked(False)

    def _interval_bounds(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        start_date = self.start_date_combo.currentData()
        start_time = self.start_time_combo.currentData()
        end_date = self.end_date_combo.currentData()
        end_time = self.end_time_combo.currentData()
        if not start_date or not start_time or not end_date or not end_time:
            raise ValueError("Selecione data e hora inicial/final válidas.")
        start = resolve_time_option(self.detected_days, start_date, start_time)
        end = resolve_time_option(self.detected_days, end_date, end_time)
        if end < start:
            raise ValueError("A data/hora final deve ser maior ou igual à inicial.")
        return start, end

    def _export_days_for_interval(self, start: pd.Timestamp, end: pd.Timestamp) -> list[DetectedDay]:
        indexes = selected_day_indexes_for_range(
            self.detected_days,
            start.normalize(),
            end.normalize(),
        )
        return [self.detected_days[index] for index in indexes]

    def _on_day_selected(self, index: int):
        if index <= 0:
            self._prepare_full_measurement()
            return

        day_index = self.day_combo.currentData()
        if day_index is not None:
            self._select_day(int(day_index))

    def _on_date_range_changed(self, index: int):
        self._update_day_range_highlight()

    def _on_day_row_clicked(self, row: int, column: int):
        self._select_day(row)

    def _on_day_drag_range_changed(self, start_row: int, end_row: int):
        self._select_day_range(start_row, end_row)

    def _prepare_full_measurement(self):
        if self.original_processed is None:
            return

        try:
            start, end = get_measurement_bounds(self.original_processed.dataframe)
        except Exception:
            return

        self.day_combo.blockSignals(True)
        self.start_date_combo.blockSignals(True)
        self.end_date_combo.blockSignals(True)
        try:
            self.day_combo.setCurrentIndex(0)
            self._set_combo_value(self.start_date_combo, pd.Timestamp(start).strftime("%Y-%m-%d"))
            self._set_combo_value(self.end_date_combo, pd.Timestamp(end).strftime("%Y-%m-%d"))
            self._set_combo_value(self.start_time_combo, FIRST_RECORD_OF_DAY)
            self._set_combo_value(self.end_time_combo, LAST_RECORD_OF_DAY)
        finally:
            self.day_combo.blockSignals(False)
            self.start_date_combo.blockSignals(False)
            self.end_date_combo.blockSignals(False)

        self.days_table.clearSelection()
        self._update_day_range_highlight()

    def _select_day(self, day_index: int):
        self._select_day_range(day_index, day_index)

        combo_index = self.day_combo.findData(day_index)
        if combo_index >= 0 and self.day_combo.currentIndex() != combo_index:
            self.day_combo.blockSignals(True)
            try:
                self.day_combo.setCurrentIndex(combo_index)
            finally:
                self.day_combo.blockSignals(False)

    def _select_day_range(self, start_row: int, end_row: int):
        if not self.detected_days:
            return

        first_row = max(0, min(start_row, end_row))
        last_row = min(len(self.detected_days) - 1, max(start_row, end_row))
        if first_row > last_row:
            return

        start_day = self.detected_days[first_row]
        end_day = self.detected_days[last_row]

        self.start_date_combo.blockSignals(True)
        self.end_date_combo.blockSignals(True)
        try:
            self._set_combo_value(
                self.start_date_combo,
                pd.Timestamp(start_day.date).strftime("%Y-%m-%d"),
            )
            self._set_combo_value(
                self.end_date_combo,
                pd.Timestamp(end_day.date).strftime("%Y-%m-%d"),
            )
            self._set_combo_value(self.start_time_combo, FIRST_RECORD_OF_DAY)
            self._set_combo_value(self.end_time_combo, LAST_RECORD_OF_DAY)
        finally:
            self.start_date_combo.blockSignals(False)
            self.end_date_combo.blockSignals(False)

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

    def build_export_config(self) -> dict | None:
        graphs = self._selected_graphs()
        if not graphs:
            QMessageBox.warning(self, "Validação", "Selecione pelo menos um gráfico.")
            return None

        scope = "full"
        try:
            start, end = self._interval_bounds()
        except Exception as exc:
            QMessageBox.warning(self, "Validação", str(exc))
            return None

        days = self._export_days_for_interval(start, end)
        if not days:
            QMessageBox.warning(
                self,
                "Validação",
                "O intervalo selecionado não contém dias detectados."
            )
            return None

        if (
            self.original_processed is not None
            and not filter_matches_measurement_bounds(
                self.original_processed.dataframe,
                custom_time_filter(start, end),
            )
        ):
            scope = "interval"

        return {
            "scope": scope,
            "mode": "daily" if self.mode_daily_radio.isChecked() else "single",
            "start": start,
            "end": end,
            "days": days,
            "graphs": graphs,
        }


def format_pdf_success_message(pdf_paths: list[str], output_dir: Path | None = None) -> str:
    count = len(pdf_paths)
    if count == 1:
        return f"1 PDF gerado com sucesso.\n\nLocal:\n{pdf_paths[0]}"

    folder = str(output_dir) if output_dir is not None else ""
    return f"{count} PDFs gerados com sucesso.\n\nPasta:\n{folder}"


def format_export_canceled_message() -> str:
    return "A exportação foi interrompida pelo usuário."


def format_export_error_message(error_details: str) -> str:
    return f"Não foi possível concluir a exportação.\n\n{error_details}"


class ExportTitleCustomizationPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("PERSONALIZAR TÍTULO", parent)
        self.original_processed: ProcessedData | None = None
        self.fields: dict[str, QLineEdit] = {}
        self._build_ui()
        self.refresh_context(None)

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        radio_layout = QHBoxLayout()
        radio_layout.addWidget(QLabel("Usar título personalizado?"))
        self.no_radio = QRadioButton("NÃO")
        self.yes_radio = QRadioButton("SIM")
        self.no_radio.setChecked(True)
        self.no_radio.toggled.connect(self._on_mode_changed)
        self.yes_radio.toggled.connect(self._on_mode_changed)
        radio_layout.addWidget(self.no_radio)
        radio_layout.addWidget(self.yes_radio)
        radio_layout.addStretch()
        layout.addLayout(radio_layout)

        self.fields_layout = QVBoxLayout()
        self.fields_layout.setSpacing(6)

        first_row = QGridLayout()
        first_row.setHorizontalSpacing(10)
        first_row.setVerticalSpacing(4)
        second_row = QGridLayout()
        second_row.setHorizontalSpacing(10)
        second_row.setVerticalSpacing(4)

        field_specs = [
            (first_row, "company", "Empresa", 0),
            (first_row, "city", "Cidade/ES", 1),
            (first_row, "display_integration_text", "Integralização", 2),
            (first_row, "revision", "Revisão", 3),
            (second_row, "local", "Local", 0),
            (second_row, "equipment_reference", "Referência / Tag", 1),
            (second_row, "equipment_value", "Potência (kVA)", 2),
        ]
        for row_layout, key, label, column in field_specs:
            label_widget = QLabel(label)
            input_widget = QLineEdit()
            input_widget.setMinimumHeight(26)
            input_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.fields[key] = input_widget
            if key == "equipment_value":
                self.equipment_value_label = label_widget
            row_layout.addWidget(label_widget, 0, column)
            row_layout.addWidget(input_widget, 1, column)

        for column in range(4):
            first_row.setColumnStretch(column, 1)
        for column in range(3):
            second_row.setColumnStretch(column, 1)
        self.fields_layout.addLayout(first_row)
        self.fields_layout.addLayout(second_row)
        layout.addLayout(self.fields_layout)
        self._configure_field_validation()
        self.setLayout(layout)

        self.setStyleSheet("""
            QGroupBox {
                color: #f1f1f1;
                border: 1px solid #333333;
                border-radius: 8px;
                margin-top: 12px;
                padding: 8px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel, QRadioButton {
                color: #f1f1f1;
                background-color: transparent;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border-radius: 7px;
                border: 1px solid #777777;
                background-color: #111111;
            }
            QRadioButton::indicator:checked {
                border: 1px solid #2d6cdf;
                background-color: #2d6cdf;
            }
            QLineEdit {
                background-color: #111111;
                color: #f1f1f1;
                border: 1px solid #2d6cdf;
                border-radius: 4px;
                padding: 5px;
            }
            QLineEdit:disabled {
                background-color: #0b0b0b;
                color: #777777;
                border: 1px solid #333333;
            }
        """)

    def _configure_field_validation(self):
        for key in ("company", "city", "local", "equipment_reference"):
            enable_uppercase_input(self.fields[key])

        set_digits_only_validator(self.fields["revision"])
        set_decimal_number_validator(self.fields["equipment_value"])

    def refresh_context(self, processed: ProcessedData | None):
        self.original_processed = processed
        self.no_radio.setChecked(True)
        self._populate_from_processed()
        self._update_enabled_state()

    def _on_mode_changed(self):
        if self.no_radio.isChecked():
            self._populate_from_processed()
        self._update_enabled_state()

    def _populate_from_processed(self):
        processed = self.original_processed
        values = {
            "company": processed.company if processed else "",
            "city": processed.city if processed else "",
            "display_integration_text": processed.integration_display_text() if processed else "",
            "revision": processed.revision if processed else "",
            "local": processed.local if processed else "",
            "equipment_reference": processed.equipment_reference if processed else "",
            "equipment_value": format_numeric_value(processed.equipment_value) if processed else "",
        }
        for key, value in values.items():
            self.fields[key].setText(str(value or ""))
        self._update_equipment_value_label()

    def _update_equipment_value_label(self):
        label_text = "Corrente (A)" if self._is_breaker() else "Potência (kVA)"
        self.equipment_value_label.setText(label_text)

    def _is_breaker(self) -> bool:
        return bool(
            self.original_processed
            and self.original_processed.equipment_type == "DISJUNTOR"
        )

    def _update_enabled_state(self):
        enabled = self.yes_radio.isChecked()
        for field in self.fields.values():
            field.setEnabled(enabled)

    def metadata(self) -> dict:
        processed = self.original_processed
        if processed is None or self.no_radio.isChecked():
            if processed is None:
                return {}
            return {
                "company": processed.company,
                "city": processed.city,
                "revision": processed.revision,
                "local": processed.local,
                "equipment_reference": processed.equipment_reference,
                "equipment_value": processed.equipment_value,
                "equipment_type": processed.equipment_type,
                "display_integration_text": processed.integration_display_text(),
            }

        return {
            "company": self.fields["company"].text().strip().upper(),
            "city": self.fields["city"].text().strip().upper(),
            "display_integration_text": self.fields["display_integration_text"].text().strip(),
            "revision": self.fields["revision"].text().strip(),
            "local": self.fields["local"].text().strip().upper(),
            "equipment_reference": self.fields["equipment_reference"].text().strip().upper(),
            "equipment_value": self.fields["equipment_value"].text().strip().replace(",", "."),
            "equipment_type": processed.equipment_type,
        }


class PdfExportTab(QWidget):
    def __init__(self, graph_page):
        super().__init__()
        self.graph_page = graph_page
        self.checkboxes: dict[str, QCheckBox] = {}
        self.default_pdf_graphs = DEFAULT_PDF_GRAPHS
        self._pdf_thread: QThread | None = None
        self._pdf_worker: PdfExportWorker | None = None
        self._daily_pdf_thread: QThread | None = None
        self._daily_pdf_worker: CustomPdfExportWorker | None = None
        self._custom_export_total_files = 0
        self._custom_export_mode = ""
        self._custom_export_output_dir: Path | None = None
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

        title = QLabel("EXPORTAR MEDIÇÃO ATUAL")
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
        self.clear_all_button.clicked.connect(self.clear_all)

        self.export_button = QPushButton("EXPORTAR MEDIÇÃO ATUAL")
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

        self.cancel_standard_button = QPushButton("PARAR EXPORTAÇÃO")
        self.cancel_standard_button.setVisible(False)
        self.cancel_standard_button.setStyleSheet("""
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
        self.cancel_standard_button.clicked.connect(self.cancel_daily_export)

        self.export_daily_button = QPushButton("EXPORTAR MEDIÇÃO PERSONALIZADA")
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
            QPushButton:pressed {
                background-color: #173f7d;
            }
            QPushButton:disabled {
                background-color: #173f7d;
                color: #d0d0d0;
            }
        """)
        self.export_daily_button.clicked.connect(self.export_custom_measurement)

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
        buttons_layout.addWidget(self.cancel_standard_button)

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
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidget(checklist_container)

        left_column = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 12, 0)
        left_layout.setSpacing(12)
        left_layout.addWidget(title)
        left_layout.addWidget(subtitle)
        left_layout.addWidget(scroll_area, 1)
        left_layout.addLayout(buttons_layout)
        left_column.setLayout(left_layout)

        self.custom_export_panel = CustomMeasurementExportPanel(
            self,
            self.graph_page.original_processed,
            self.graph_page.time_selection_tab.detected_days,
            self._selected_graphs(),
        )

        custom_buttons_layout = QVBoxLayout()
        custom_buttons_layout.setContentsMargins(18, 0, 18, 18)
        custom_buttons_layout.setSpacing(10)
        custom_buttons_layout.addWidget(self.export_daily_button)
        custom_buttons_layout.addWidget(self.cancel_daily_button)

        right_container = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        right_layout.addWidget(self.custom_export_panel, 1)
        right_layout.addLayout(custom_buttons_layout)
        right_container.setLayout(right_layout)
        right_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        right_scroll_area = QScrollArea()
        right_scroll_area.setWidgetResizable(True)
        right_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_scroll_area.setWidget(right_container)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        separator.setStyleSheet("color: #2a2a2a; background-color: #2a2a2a;")
        separator.setFixedWidth(1)

        columns_layout = QHBoxLayout()
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(14)
        columns_layout.addWidget(left_column, 1)
        columns_layout.addWidget(separator)
        columns_layout.addWidget(right_scroll_area, 1)

        root_layout.addLayout(columns_layout, 1)
        self.title_customization_panel = ExportTitleCustomizationPanel(self)
        root_layout.addWidget(self.title_customization_panel)
        root_layout.addWidget(self.status_label)
        root_layout.addWidget(self.progress_bar)

        self.setLayout(root_layout)

    def set_exporting_state(self, exporting: bool):
        self.export_button.setDisabled(exporting)
        self.export_daily_button.setDisabled(exporting)
        self.select_default_button.setDisabled(exporting)
        self.select_all_button.setDisabled(exporting)
        self.clear_all_button.setDisabled(exporting)
        self.custom_export_panel.setDisabled(exporting)
        self.title_customization_panel.setDisabled(exporting)

        for checkbox in self.checkboxes.values():
            checkbox.setDisabled(exporting)

        self.progress_bar.setVisible(exporting)
        self.status_label.setVisible(exporting)

        if exporting:
            self.export_button.setText("EXPORTANDO MEDIÇÃO ATUAL...")
            self.status_label.setText("Processando gráficos e montando o arquivo PDF. Aguarde...")
        else:
            self.export_button.setText("EXPORTAR MEDIÇÃO ATUAL")
            self.export_daily_button.setText("EXPORTAR MEDIÇÃO PERSONALIZADA")
            self.cancel_standard_button.setVisible(False)
            self.cancel_standard_button.setEnabled(False)
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

    def refresh_custom_export_context(self):
        self.custom_export_panel.refresh_context(
            self.graph_page.original_processed,
            self.graph_page.time_selection_tab.detected_days,
        )
        self.title_customization_panel.refresh_context(self.graph_page.original_processed)

    def _ensure_custom_export_context_current(self):
        detected_days = tuple(self.graph_page.time_selection_tab.detected_days)
        if (
            self.custom_export_panel.original_processed is not self.graph_page.original_processed
            or self.custom_export_panel.detected_days != detected_days
        ):
            self.custom_export_panel.refresh_context(
                self.graph_page.original_processed,
                detected_days,
            )
            self.title_customization_panel.refresh_context(self.graph_page.original_processed)

    def _selected_graphs(self) -> list[str]:
        return [
            name for name, checkbox in self.checkboxes.items()
            if checkbox.isChecked()
        ]

    def _export_metadata(self) -> dict:
        return self.title_customization_panel.metadata()

    def _processed_with_export_metadata(
        self,
        processed: ProcessedData,
        metadata: dict,
        dataframe: pd.DataFrame | None = None,
    ) -> ProcessedData:
        export_processed = ProcessedData(
            company=metadata.get("company", processed.company),
            city=metadata.get("city", processed.city),
            trafo=processed.trafo,
            local=metadata.get("local", processed.local),
            revision=metadata.get("revision", processed.revision),
            excel_path=processed.excel_path,
            dataframe=processed.dataframe if dataframe is None else dataframe,
            integration_time=processed.integration_time,
            tension=processed.tension,
            equipment_type=processed.equipment_type,
            equipment_reference=processed.equipment_reference,
            equipment_value=processed.equipment_value,
        )
        export_processed.display_equipment_reference = metadata.get(
            "equipment_reference",
            processed.equipment_reference,
        )
        export_processed.display_equipment_value = metadata.get(
            "equipment_value",
            processed.equipment_value,
        )
        export_processed.display_integration_text = metadata.get(
            "display_integration_text",
            processed.integration_display_text(),
        )
        return export_processed

    @staticmethod
    def _filename_metadata(metadata: dict) -> dict:
        return {
            "local": metadata.get("local"),
            "equipment_reference": metadata.get("equipment_reference"),
            "equipment_type": metadata.get("equipment_type"),
            "equipment_value": metadata.get("equipment_value"),
        }

    def _validate_pdf_preflight(
        self,
        selected_graphs: list[str],
        output_dir: Path | None = None,
        require_detected_days: bool = False,
    ) -> bool:
        if not selected_graphs:
            QMessageBox.warning(
                self,
                "Exportar medição atual",
                "Selecione pelo menos um gráfico para exportação."
            )
            return False

        if not self.graph_page.current_processed:
            QMessageBox.warning(
                self,
                "Exportar medição atual",
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
                "Exportar medição atual",
                f"A pasta de destino não está disponível para gravação:\n\n{exc}"
                )
                return False

        try:
            with tempfile.TemporaryDirectory(prefix="mug_pdf_preflight_"):
                pass
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Exportar medição atual",
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
            export_metadata = self._export_metadata()

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

                processed_for_pdf = self._processed_with_export_metadata(
                    processed,
                    export_metadata,
                    dataframe=df,
                )
            else:
                processed_for_pdf = self._processed_with_export_metadata(
                    processed,
                    export_metadata,
                )

            pdf_filename = build_custom_pdf_filename(
                export_metadata.get("company", processed.company),
                export_metadata.get("revision", processed.revision),
                **self._filename_metadata(export_metadata),
            )

            self.set_exporting_state(True)
            self.cancel_standard_button.setVisible(True)
            self.cancel_standard_button.setEnabled(True)

            self._pdf_thread = QThread()
            self._pdf_worker = PdfExportWorker(
                processed=processed_for_pdf,
                selected_graphs=selected_graphs,
                output_dir=Path(output_dir),
                zoom_mode=zoom_mode,
                pdf_filename=pdf_filename,
            )
            self._pdf_worker.moveToThread(self._pdf_thread)

            self._pdf_thread.started.connect(self._pdf_worker.run)
            self._pdf_worker.finished.connect(self._on_pdf_finished)
            self._pdf_worker.error.connect(self._on_pdf_error)
            self._pdf_worker.canceled.connect(self._on_pdf_canceled)
            self._pdf_worker.finished.connect(self._pdf_thread.quit)
            self._pdf_worker.error.connect(self._pdf_thread.quit)
            self._pdf_worker.canceled.connect(self._pdf_thread.quit)
            self._pdf_thread.finished.connect(self._pdf_worker.deleteLater)
            self._pdf_thread.finished.connect(self._pdf_thread.deleteLater)
            self._pdf_thread.finished.connect(self._clear_pdf_thread_refs)
            self._pdf_thread.start()

        except Exception as e:
            self.set_exporting_state(False)
            QMessageBox.critical(
                self,
                "ERRO NA EXPORTAÇÃO",
                format_export_error_message(str(e))
            )

    def _processed_for_dataframe(
        self,
        dataframe: pd.DataFrame,
        metadata: dict | None = None,
    ) -> ProcessedData:
        original = self.graph_page.original_processed
        if original is None:
            raise ValueError("Nenhuma medição original está disponível.")

        return self._processed_with_export_metadata(
            original,
            metadata or self._export_metadata(),
            dataframe=dataframe,
        )

    def _filtered_dataframe_for_bounds(self, start, end) -> pd.DataFrame:
        if self.graph_page.original_dataframe is None:
            raise ValueError("Nenhuma medição original está disponível.")

        dataframe = apply_time_filter(
            self.graph_page.original_dataframe,
            custom_time_filter(start, end),
        )
        if dataframe.empty:
            raise ValueError("O intervalo selecionado não possui registros de medição.")
        return dataframe

    def _dataframe_for_days(self, days: list[DetectedDay]) -> pd.DataFrame:
        frames = [
            self._filtered_dataframe_for_bounds(day.start_datetime, day.end_datetime)
            for day in days
        ]
        if not frames:
            raise ValueError("Nenhum dia foi selecionado.")
        return pd.concat(frames, ignore_index=True).sort_values("Datetime")

    def _build_custom_export_tasks(self, config: dict) -> list[dict]:
        original = self.graph_page.original_processed
        if original is None:
            raise ValueError("Nenhuma medição original está disponível.")

        company = original.company
        revision = original.revision
        output_dir = Path(config["output_dir"])
        export_metadata = config["metadata"]
        company = export_metadata.get("company", company)
        revision = export_metadata.get("revision", revision)
        filename_metadata = self._filename_metadata(export_metadata)

        if config["mode"] == "daily":
            tasks: list[dict] = []
            export_timestamp = pd.Timestamp.now()
            filenames = [
                build_daily_pdf_filename(
                    company,
                    revision,
                    day.date,
                    export_timestamp,
                    **filename_metadata,
                )
                for day in config["days"]
            ]
            output_paths = reserve_unique_pdf_paths(output_dir, filenames)
            for day, filename, output_path in zip(config["days"], filenames, output_paths):
                start = max(pd.Timestamp(day.start_datetime), pd.Timestamp(config["start"]))
                end = min(pd.Timestamp(day.end_datetime), pd.Timestamp(config["end"]))
                if end < start:
                    continue
                dataframe = self._filtered_dataframe_for_bounds(
                    start,
                    end,
                )
                tasks.append({
                    "label": day.label,
                    "processed": self._processed_for_dataframe(dataframe, export_metadata),
                    "filename": filename,
                    "output_path": output_path,
                })
            return tasks

        if config["scope"] == "full":
            dataframe = self.graph_page.original_dataframe.copy()
        elif config["scope"] == "interval":
            dataframe = self._filtered_dataframe_for_bounds(
                config["start"],
                config["end"],
            )
        else:
            dataframe = self._dataframe_for_days(config["days"])

        filename = build_custom_pdf_filename(
            company,
            revision,
            **filename_metadata,
        )
        output_path = reserve_unique_pdf_paths(output_dir, [filename])[0]

        return [{
            "label": "Medição personalizada",
            "processed": self._processed_for_dataframe(dataframe, export_metadata),
            "filename": filename,
            "output_path": output_path,
        }]

    def export_custom_measurement(self):
        if not self.graph_page.current_processed:
            QMessageBox.warning(
                self,
                "Exportar medição personalizada",
                "Nenhum gráfico foi carregado ainda."
            )
            return

        if not self.graph_page.time_selection_tab.detected_days:
            QMessageBox.warning(
                self,
                "Exportar medição personalizada",
                "Nenhum dia de medição foi detectado para exportação personalizada."
            )
            return

        if self.graph_page.original_processed is None:
            QMessageBox.warning(
                self,
                "Exportar medição personalizada",
                "Nenhuma medição original está disponível para exportação personalizada."
            )
            return

        self._ensure_custom_export_context_current()

        config = self.custom_export_panel.build_export_config()
        if not config:
            return
        config["metadata"] = self._export_metadata()

        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de destino"
        )

        if not output_dir:
            return

        config["output_dir"] = Path(output_dir)

        if not self._validate_pdf_preflight(
            config["graphs"],
            config["output_dir"],
            require_detected_days=True,
        ):
            return

        try:
            tasks = self._build_custom_export_tasks(config)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Exportar medição personalizada",
                f"Não foi possível preparar a exportação:\n\n{exc}"
            )
            return

        if not tasks:
            QMessageBox.warning(
                self,
                "Exportar medição personalizada",
                "Nenhum arquivo foi preparado para exportação."
            )
            return

        self._custom_export_total_files = len(tasks)
        self._custom_export_mode = config["mode"]
        self._custom_export_output_dir = config["output_dir"]

        self.set_exporting_state(True)
        self.export_button.setText("EXPORTANDO MEDIÇÃO ATUAL...")
        self.export_daily_button.setText("EXPORTANDO MEDIÇÃO...")
        self.cancel_daily_button.setVisible(True)
        self.cancel_daily_button.setEnabled(True)
        self.status_label.setText("Preparando exportação personalizada. Aguarde...")

        self._daily_pdf_thread = QThread()
        self._daily_pdf_worker = CustomPdfExportWorker(
            export_tasks=tasks,
            selected_graphs=config["graphs"],
            output_dir=config["output_dir"],
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
        if self._daily_pdf_worker is not None:
            self._daily_pdf_worker.request_cancel()
        elif self._pdf_worker is not None:
            self._pdf_worker.request_cancel()
        else:
            return

        self.cancel_standard_button.setEnabled(False)
        self.cancel_daily_button.setEnabled(False)
        self.status_label.setText("Cancelando exportação...")

    def _on_pdf_finished(self, pdf_path: str):
        self.set_exporting_state(False)
        QMessageBox.information(
            self,
            "EXPORTAÇÃO CONCLUÍDA",
            format_pdf_success_message([pdf_path])
        )

    def _on_pdf_error(self, error_message: str):
        self.set_exporting_state(False)
        QMessageBox.critical(
            self,
            "ERRO NA EXPORTAÇÃO",
            format_export_error_message(error_message)
        )

    def _on_pdf_canceled(self):
        self.set_exporting_state(False)
        QMessageBox.warning(
            self,
            "EXPORTAÇÃO CANCELADA",
            format_export_canceled_message()
        )

    def _clear_pdf_thread_refs(self):
        self._pdf_thread = None
        self._pdf_worker = None

    def _on_daily_pdf_progress(self, current: int, total: int, day_label: str):
        if self._custom_export_mode == "daily":
            self.status_label.setText(
                f"Exportando PDF diário {current} de {total}...\n{day_label}"
            )
        else:
            self.status_label.setText(
                f"Exportando PDF personalizado {current} de {total}...\n{day_label}"
            )

    def _on_daily_pdf_finished(self, successes: list, failures: list, canceled: bool):
        self.set_exporting_state(False)

        if canceled:
            QMessageBox.warning(
                self,
                "EXPORTAÇÃO CANCELADA",
                format_export_canceled_message()
            )
            return

        if failures:
            details = (
                f"PDFs gerados com sucesso: {len(successes)}\n\n"
                "Falhas:\n" + "\n".join(str(item) for item in failures)
            )
            QMessageBox.critical(
                self,
                "ERRO NA EXPORTAÇÃO",
                format_export_error_message(details)
            )
            return

        QMessageBox.information(
            self,
            "EXPORTAÇÃO CONCLUÍDA",
            format_pdf_success_message(successes, self._custom_export_output_dir)
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
        self._graph_cache: dict[tuple, go.Figure] = {}
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

        graph_builders = {
            "Tensão": create_tension_graph,
            "Corrente": create_current_graph,
            "Potência Ativa": create_active_power_graph,
            "Potência Aparente": create_apparent_power_graph,
            "Fator de Potência": create_pf_graph,
            "Deseq. Tensão": create_tension_imbalance_graph,
            "Deseq. Corrente": create_current_imbalance_graph,
            "Consumo": create_consumption_graph,
            "DHT Tensão": create_dht_voltage_graph,
            "DHT Corrente": create_dht_current_graph,
            "Tensão x Corrente": create_combined_vxi_graph,
            "kW x kVA": create_combined_kwxkva_graph,
        }

        figures = {}
        base_key = self._graph_cache_base_key(processed, df, x_min, x_max, zoom_mode)

        for name, builder in graph_builders.items():
            cache_key = (name, *base_key)
            cached = self._graph_cache.get(cache_key)
            if cached is not None:
                figures[name] = go.Figure(cached)
                continue

            fig = builder(filtered_processed, show_logo=False)
            fig = self._apply_interface_visual_standard(
                graph_name=name,
                fig=fig,
                dataframe=df,
                zoom_mode=zoom_mode,
            )
            self._graph_cache[cache_key] = go.Figure(fig)
            figures[name] = fig


        return figures, df

    def _graph_cache_base_key(
        self,
        processed: ProcessedData,
        dataframe: pd.DataFrame,
        x_min,
        x_max,
        zoom_mode: bool,
    ) -> tuple:
        if dataframe.empty:
            start = None
            end = None
        else:
            start = str(pd.Timestamp(dataframe["Datetime"].iloc[0]))
            end = str(pd.Timestamp(dataframe["Datetime"].iloc[-1]))

        return (
            id(processed.dataframe),
            len(dataframe),
            start,
            end,
            str(x_min) if x_min is not None else None,
            str(x_max) if x_max is not None else None,
            zoom_mode,
            processed.company,
            processed.revision,
            processed.tension,
            processed.equipment_type,
            processed.equipment_reference,
            processed.equipment_value,
        )

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
            self._graph_cache.clear()
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
        self._graph_cache.clear()
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
        self.pdf_export_tab.refresh_custom_export_context()
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
            self._graph_cache.clear()
            self.current_x_min = None
            self.current_x_max = None

            try:
                self.time_selection_tab.load_processed_data(self.original_processed)
                self.pdf_export_tab.refresh_custom_export_context()
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
