from pathlib import Path
import io
import os
import sys
import tempfile
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
from PIL import Image
from plotly.io import to_image

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
from core.profiling import profile_block, log_profile_event


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


FIXED_Y_SUBDIVISIONS = 20

FIXED_28_Y_GRAPHS = [
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


LEFT_MARGIN_MM = 10
TOP_MARGIN_MM = 10
RIGHT_MARGIN_MM = 5
BOTTOM_MARGIN_MM = 5

A4_LANDSCAPE_WIDTH_MM = 297
A4_LANDSCAPE_HEIGHT_MM = 210


EMBEDDED_BROWSER_RELATIVE_CANDIDATES = [
    Path("browser") / "chrome" / "chrome.exe",
    Path("browser") / "chrome.exe",
    Path("browser") / "chromium.exe",
    Path("browser") / "chrome-win64" / "chrome.exe",
    Path("browser") / "chrome-win" / "chrome.exe",
    Path("chromium") / "chrome.exe",
    Path("chromium") / "chromium.exe",
    Path("chrome-win64") / "chrome.exe",
]


def get_runtime_base_dirs() -> list[Path]:
    """
    Retorna diretórios-base possíveis em execução normal e em app empacotado.

    Em build PyInstaller --onedir, os dados adicionados via --add-data normalmente
    ficam dentro de sys._MEIPASS, que aponta para a pasta _internal.
    O executável fica um nível acima, em dist/MUG.
    """
    base_dirs: list[Path] = []

    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        base_dirs.append(executable_dir)

        pyinstaller_internal_dir = Path(getattr(sys, "_MEIPASS", executable_dir)).resolve()
        base_dirs.append(pyinstaller_internal_dir)
    else:
        # core/pdf_exporter.py -> raiz do projeto MUG
        project_root = Path(__file__).resolve().parents[1]
        base_dirs.append(project_root)

    # Remove duplicados preservando a ordem.
    unique_dirs: list[Path] = []
    for base_dir in base_dirs:
        if base_dir not in unique_dirs:
            unique_dirs.append(base_dir)

    return unique_dirs


def find_embedded_browser_executable() -> Path | None:
    """
    Procura um Chrome/Chromium portátil empacotado junto com a aplicação.

    Caminhos esperados, por exemplo:
    - MUG/browser/chrome.exe
    - MUG/_internal/browser/chrome.exe
    - MUG/_internal/browser/chrome-win64/chrome.exe
    """
    for base_dir in get_runtime_base_dirs():
        for relative_path in EMBEDDED_BROWSER_RELATIVE_CANDIDATES:
            browser_path = base_dir / relative_path
            if browser_path.exists() and browser_path.is_file():
                return browser_path

    return None


def configure_kaleido_browser_path() -> Path | None:
    """
    Configura o navegador usado pelo Kaleido/Choreographer.

    Kaleido v1 não inclui mais Chrome internamente. Por isso, quando existir
    um navegador portátil empacotado com o MUG, definimos BROWSER_PATH para
    evitar dependência do Chrome instalado na máquina do cliente.
    """
    embedded_browser = find_embedded_browser_executable()

    if embedded_browser is not None:
        os.environ["BROWSER_PATH"] = str(embedded_browser)
        return embedded_browser

    return None



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


def apply_fixed_28_y_subdivisions(fig: go.Figure):
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

            final_y_range = final_y_max - final_y_min
            if final_y_range <= 0:
                continue

            dtick = final_y_range / FIXED_Y_SUBDIVISIONS

            fig.layout[layout_axis].autorange = False
            fig.layout[layout_axis].range = [
                final_y_min,
                final_y_max,
            ]
            fig.layout[layout_axis].tickmode = "linear"
            fig.layout[layout_axis].tick0 = final_y_min
            fig.layout[layout_axis].dtick = dtick

    except Exception:
        pass

    return fig


def apply_pdf_visual_standard(graph_name: str, fig: go.Figure, processed, zoom_mode: bool = False):
    if graph_name == "Consumo":
        return apply_fixed_28_y_subdivisions(fig)

    fig = apply_default_x_density(fig, processed.dataframe)

    if zoom_mode:
        if graph_name != "Fator de Potência":
            fig = apply_zoom_y_autorange(fig)
        return fig

    if graph_name in FIXED_28_Y_GRAPHS:
        fig = apply_fixed_28_y_subdivisions(fig)

    return fig


def build_pdf_figures(processed, zoom_mode: bool = False, selected_graphs: list[str] | None = None) -> dict[str, object]:
    """
    Monta apenas os gráficos necessários para o PDF.

    Antes, todos os 11 gráficos eram reconstruídos mesmo quando o usuário
    selecionava poucos itens. Isso aumentava o tempo de exportação sem necessidade.
    """
    selected_set = set(selected_graphs or GRAPH_EXPORT_ORDER)

    with profile_block(
        "PDF build figures",
        selected=len(selected_set),
        zoom=zoom_mode,
        rows=len(processed.dataframe),
    ):
        builders = {
            "Tensão": lambda: create_tension_graph(processed, show_logo=True),
            "Corrente": lambda: create_current_graph(processed, show_logo=True),
            "Potência Ativa": lambda: create_active_power_graph(processed, show_logo=True),
            "Potência Aparente": lambda: create_apparent_power_graph(processed, show_logo=True),
            "Fator de Potência": lambda: create_pf_graph(processed, show_logo=True),
            "Deseq. Tensão": lambda: create_tension_imbalance_graph(processed, show_logo=True),
            "Deseq. Corrente": lambda: create_current_imbalance_graph(processed, show_logo=True),
            "Consumo": lambda: create_consumption_graph(processed, show_logo=True),
            "DHT Tensão": lambda: create_dht_voltage_graph(processed, show_logo=True),
            "DHT Corrente": lambda: create_dht_current_graph(processed, show_logo=True),
            "Tensão x Corrente": lambda: create_combined_vxi_graph(processed, show_logo=True),
            "kW x kVA": lambda: create_combined_kwxkva_graph(processed, show_logo=True),
        }

        figures = {}

        for graph_name in GRAPH_EXPORT_ORDER:
            if graph_name not in selected_set:
                continue

            builder = builders.get(graph_name)
            if builder is None:
                continue

            with profile_block("PDF graph build", graph=graph_name, zoom=zoom_mode):
                fig = builder()
                figures[graph_name] = apply_pdf_visual_standard(
                    graph_name=graph_name,
                    fig=fig,
                    processed=processed,
                    zoom_mode=zoom_mode,
                )

        return figures


def save_figure_as_jpeg(fig, output_path: Path, graph_name: str | None = None) -> Path:
    with profile_block("PDF graph image render", graph=graph_name):
        embedded_browser = configure_kaleido_browser_path()

        try:
            image_stream = io.BytesIO(
                to_image(fig, format="png", width=1250, height=884, scale=1.35)
            )
        except Exception as exc:
            browser_info = (
                f"Navegador portátil localizado em: {embedded_browser}"
                if embedded_browser is not None
                else "Nenhum navegador portátil foi localizado junto com o MUG."
            )

            raise RuntimeError(
                "Falha ao renderizar o gráfico para exportação em PDF. "
                "O MUG utiliza Plotly/Kaleido para converter os gráficos em imagens. "
                f"{browser_info} "
                "Se esta versão ainda não estiver com Chromium portátil empacotado, "
                "será necessário usar uma instalação funcional do Google Chrome/Chromium "
                "na máquina do cliente."
            ) from exc

        image_stream.seek(0)

        image = Image.open(image_stream)
        if image.mode == "RGBA":
            image = image.convert("RGB")

        image.save(output_path, "JPEG")
        return output_path


def build_pdf_filename(company: str, revision: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_company = company.strip().replace("/", "-").replace("\\", "-")
    return f"GR - {safe_company} - {timestamp} - REV{revision}.pdf"


def export_figures_to_pdf(
    processed,
    selected_graphs: list[str],
    output_dir: Path,
    zoom_mode: bool = False,
) -> Path:
    with profile_block(
        "PDF export total",
        selected=len(selected_graphs),
        zoom=zoom_mode,
        rows=len(processed.dataframe),
    ):
        output_dir.mkdir(parents=True, exist_ok=True)

        pdf = FPDF(orientation="L", unit="mm", format="A4")

        temp_dir = Path(tempfile.mkdtemp(prefix="graphs_pdf_"))
        temp_images: list[Path] = []

        try:
            figures = build_pdf_figures(processed, zoom_mode=zoom_mode, selected_graphs=selected_graphs)

            usable_width = A4_LANDSCAPE_WIDTH_MM - (LEFT_MARGIN_MM + RIGHT_MARGIN_MM)
            usable_height = A4_LANDSCAPE_HEIGHT_MM - (TOP_MARGIN_MM + BOTTOM_MARGIN_MM)

            for graph_name in GRAPH_EXPORT_ORDER:
                if graph_name not in selected_graphs:
                    continue

                fig = figures.get(graph_name)
                if fig is None:
                    continue

                with profile_block("PDF graph export page", graph=graph_name):
                    temp_image_path = temp_dir / f"{graph_name.replace(' ', '_')}.jpg"
                    save_figure_as_jpeg(fig, temp_image_path, graph_name=graph_name)
                    temp_images.append(temp_image_path)

                    pdf.add_page()

                    pdf.image(
                        str(temp_image_path),
                        x=LEFT_MARGIN_MM,
                        y=TOP_MARGIN_MM,
                        w=usable_width,
                        h=usable_height,
                    )

            if not temp_images:
                raise ValueError("Nenhum gráfico foi selecionado para exportação.")

            pdf_filename = build_pdf_filename(processed.company, processed.revision)
            pdf_path = output_dir / pdf_filename

            with profile_block("PDF file write", pages=len(temp_images), file=pdf_filename):
                pdf.output(str(pdf_path))

            log_profile_event("PDF export complete", file=pdf_path)
            return pdf_path

        finally:
            for image_path in temp_images:
                if image_path.exists():
                    image_path.unlink(missing_ok=True)

            if temp_dir.exists():
                try:
                    temp_dir.rmdir()
                except OSError:
                    pass
