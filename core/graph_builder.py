import math
import base64
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.models import ProcessedData
from core.paths import get_app_assets

Y_AXIS_TITLE_STANDOFF = 18
Y_AXIS_TICK_LABEL_STANDOFF = 6
LEFT_MARGIN = 112


def image_file_to_base64(image_path: Path) -> str | None:
    if not image_path.exists():
        return None
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    suffix = image_path.suffix.lower().replace(".", "")
    if suffix == "jpg":
        suffix = "jpeg"
    return f"data:image/{suffix};base64,{encoded}"


def find_first_existing_column(df: pd.DataFrame, candidates: list[str], label: str) -> str:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    raise ValueError(f"Coluna de {label} não encontrada. Candidatas testadas: {candidates}")


def find_first_existing_column_group(
    df: pd.DataFrame,
    candidate_groups: list[tuple[list[str], list[str], dict[str, str]]],
    label: str,
) -> tuple[list[str], list[str], dict[str, str]]:
    """
    Retorna o primeiro grupo de colunas existente.
    Cada grupo é: (colunas, nomes da legenda, mapa de cores)
    """
    for columns, names, colors in candidate_groups:
        if all(col in df.columns for col in columns):
            return columns, names, colors
    flat = [cols for cols, _, _ in candidate_groups]
    raise ValueError(f"Colunas de {label} não encontradas. Grupos testados: {flat}")


def add_logo(fig: go.Figure, show_logo: bool = False) -> None:
    if not show_logo:
        return

    assets = get_app_assets()
    if not assets.logo or not assets.logo.exists():
        return

    encoded_logo = image_file_to_base64(assets.logo)
    if not encoded_logo:
        return

    fig.add_layout_image(
        dict(
            source=encoded_logo,
            xref="paper",
            yref="paper",
            x=-0.05,
            y=1.095,
            sizex=0.15,
            sizey=0.15,
            xanchor="left",
            yanchor="top",
            opacity=1.0,
            layer="above",
        )
    )


def apply_common_layout(fig: go.Figure, df: pd.DataFrame, show_logo: bool = False) -> go.Figure:
    if "Datetime" not in df.columns:
        raise ValueError("A coluna 'Datetime' não foi encontrada no DataFrame.")

    tick_spacing = max(len(df) // 25, 1)
    tickvals = df["Datetime"].iloc[::tick_spacing]
    ticktext = [dt.strftime("%d/%m - %H:%M:%S") for dt in tickvals]

    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(
            gridcolor="lightgrey",
            zerolinecolor="lightgrey",
            tickangle=270,
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            title_text="",
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
        ),
        margin=dict(l=95, r=115, t=95, b=50),
        font={"family": "Arial", "size": 12, "color": "#000000"},
        legend_title_font={"family": "Arial", "size": 11, "color": "#000000"},
        legend_font={"family": "Arial", "size": 11, "color": "#000000"},
    )
    # Evita corte de textos de máximos/mínimos nas bordas do gráfico.
    fig.update_traces(
        cliponaxis=False,
        selector=dict(mode="markers"),
    )

    add_logo(fig, show_logo=show_logo)
    return fig


def get_tension_limits(tension: str) -> tuple[float, float, float, float]:
    if tension == "220":
        return 202, 231, 191, 233
    if tension == "254":
        return 234, 267, 221, 269
    if tension == "380":
        return 350, 399, 331, 403
    if tension == "440":
        return 405, 462, 383, 466
    raise ValueError(f"Tensão nominal não suportada: {tension}")


def is_full_view(initial_view: bool | None) -> bool:
    # No app desktop atual não há callback de sincronização de zoom;
    # portanto, a renderização padrão corresponde ao "full view" do Dash antigo.
    return initial_view is not False


def _get_extreme_points(df: pd.DataFrame, columns: list[str]) -> tuple[float, float, object | None, object | None]:
    max_vals = df[columns].max()
    y_max_value = max_vals.max()
    min_vals = df[columns].min()
    y_min_value = min_vals.min()

    max_indices = df[
        pd.concat([(df[col] == y_max_value) for col in columns], axis=1).any(axis=1)
    ].index
    min_indices = df[
        pd.concat([(df[col] == y_min_value) for col in columns], axis=1).any(axis=1)
    ].index

    x_max = df.loc[max_indices[0], "Datetime"] if not max_indices.empty else None
    x_min = df.loc[min_indices[0], "Datetime"] if not min_indices.empty else None
    return y_max_value, y_min_value, x_max, x_min




def get_safe_text_position(
    x_value,
    y_value,
    df: pd.DataFrame,
    y_min: float | None = None,
    y_max: float | None = None,
    kind: str = "max",
) -> str:
    """
    Retorna uma posição limpa para rótulos de máximo/mínimo.

    Regra visual definida para o projeto:
    - máximo: acima e centralizado;
    - mínimo: abaixo e centralizado;
    - perto das bordas laterais: desloca horizontalmente para dentro;
    - valor zero: desloca lateralmente para não ficar sobre o eixo do tempo;
    - sem setas, sem linhas auxiliares e sem anotações deslocadas.
    """
    try:
        dt = pd.to_datetime(df["Datetime"])
        x_min = dt.min()
        x_max = dt.max()
        x_value = pd.to_datetime(x_value)

        total_seconds = (x_max - x_min).total_seconds()
        if total_seconds <= 0:
            x_ratio = 0.5
        else:
            x_ratio = (x_value - x_min).total_seconds() / total_seconds

        is_zero = abs(float(y_value)) < 1e-9

        # Caso especial: rótulo em zero não deve ficar centralizado sobre o eixo do tempo.
        if is_zero:
            if kind == "min":
                return "top right" if x_ratio <= 0.5 else "top left"
            return "top right" if x_ratio <= 0.5 else "top left"

        vertical = "top" if kind != "min" else "bottom"

        # Centraliza sempre que possível; só desloca nas bordas laterais.
        horizontal = "center"
        if x_ratio <= 0.08:
            horizontal = "right"
        elif x_ratio >= 0.92:
            horizontal = "left"

        return f"{vertical} {horizontal}"

    except Exception:
        return "top center" if kind != "min" else "bottom center"


def get_safe_positions_for_extremes(
    df: pd.DataFrame,
    x_max,
    y_max_value,
    x_min,
    y_min_value,
) -> tuple[str, str]:
    """
    Mantém máximo acima e mínimo abaixo. Se ambos estiverem praticamente no
    mesmo ponto, desloca horizontalmente para reduzir sobreposição.
    """
    max_position = get_safe_text_position(x_max, y_max_value, df, y_min_value, y_max_value, "max")
    min_position = get_safe_text_position(x_min, y_min_value, df, y_min_value, y_max_value, "min")

    try:
        dt = pd.to_datetime(df["Datetime"])
        total_seconds = (dt.max() - dt.min()).total_seconds()
        if total_seconds <= 0:
            return max_position, min_position

        x_gap = abs((pd.to_datetime(x_max) - pd.to_datetime(x_min)).total_seconds())
        y_range = abs(float(y_max_value) - float(y_min_value))
        y_gap = abs(float(y_max_value) - float(y_min_value))

        if x_gap / total_seconds <= 0.035 and (y_range <= 0 or y_gap / max(y_range, 1e-9) <= 0.12):
            max_position = "top right"
            min_position = "bottom left"
    except Exception:
        pass

    return max_position, min_position


def _infer_y_range_from_figure(fig: go.Figure) -> tuple[float, float]:
    """Obtém o intervalo Y real dos traçados principais do gráfico."""
    values: list[float] = []

    for trace in fig.data:
        mode = str(getattr(trace, "mode", "") or "")
        name = str(getattr(trace, "name", "") or "")

        if "lines" not in mode:
            continue
        if name.lower().startswith(("máx", "max", "mín", "min")):
            continue

        y_values = getattr(trace, "y", None)
        if y_values is None:
            continue

        numeric = pd.to_numeric(pd.Series(y_values), errors="coerce").dropna()
        if not numeric.empty:
            values.extend(numeric.astype(float).tolist())

    if not values:
        return 0.0, 1.0

    y_min = min(values)
    y_max = max(values)

    if y_max <= y_min:
        pad = abs(y_max) * 0.05 if y_max else 1.0
        return y_min - pad, y_max + pad

    return float(y_min), float(y_max)


def normalize_extreme_label_positions(
    max_position: str | None,
    min_position: str | None,
    x_max,
    x_min,
    df: pd.DataFrame,
) -> tuple[str | None, str | None]:
    """Compatibilidade interna: mantém as posições já calculadas."""
    return max_position, min_position


def add_extreme_marker(
    fig: go.Figure,
    df: pd.DataFrame,
    x_value,
    y_value,
    text: str,
    name: str,
    color: str,
    kind: str,
    y_min: float | None = None,
    y_max: float | None = None,
    forced_position: str | None = None,
) -> None:
    """
    Adiciona marcador de máximo/mínimo sem setas e sem linhas auxiliares.

    Padrão visual:
    - máximo: rótulo acima e centralizado;
    - mínimo: rótulo abaixo e centralizado;
    - perto de bordas: desloca para dentro ou inverte verticalmente para evitar corte/eixo X.
    """
    if y_min is None or y_max is None:
        inferred_min, inferred_max = _infer_y_range_from_figure(fig)
        y_min = inferred_min if y_min is None else y_min
        y_max = inferred_max if y_max is None else y_max

    position = forced_position or get_safe_text_position(
        x_value=x_value,
        y_value=y_value,
        df=df,
        y_min=float(y_min),
        y_max=float(y_max),
        kind=kind,
    )

    fig.add_trace(
        go.Scatter(
            x=[x_value],
            y=[y_value],
            mode="markers+text",
            name=name,
            text=[text],
            textposition=position,
            textfont=dict(family="Arial", size=11, color="#000000"),
            marker=dict(color=color, size=5),
            cliponaxis=False,
            hovertemplate=f"{name}: {text}<extra></extra>",
        )
    )


def copy_point_annotations(source_fig: go.Figure, target_fig: go.Figure, yref: str = "y") -> None:
    """
    Mantida por compatibilidade.

    Os rótulos de máximo/mínimo agora são traços markers+text, sem anotações,
    sem setas e sem linhas. Como os gráficos combinados já copiam os traços,
    não é necessário copiar annotations.
    """
    return None


def create_tension_graph(
    processed: ProcessedData,
    show_logo: bool = False,
    initial_view: bool | None = None,
) -> go.Figure:
    df = processed.dataframe.copy()

    column_groups = [
        (
            ["Tensao AB (médio)(V)", "Tensao BC (médio)(V)", "Tensao CA (médio)(V)"],
            ["RS (V)", "ST (V)", "TR (V)"],
            {"RS (V)": "#166cc2", "ST (V)": "#006c17", "TR (V)": "#c60003"},
        ),
        (
            ["Tensão AB (médio)(V)", "Tensão BC (médio)(V)", "Tensão CA (médio)(V)"],
            ["RS (V)", "ST (V)", "TR (V)"],
            {"RS (V)": "#166cc2", "ST (V)": "#006c17", "TR (V)": "#c60003"},
        ),
        (
            ["Tensão A (médio)(V)", "Tensão B (médio)(V)", "Tensão C (médio)(V)"],
            ["R (V)", "S (V)", "T (V)"],
            {"R (V)": "#166cc2", "S (V)": "#006c17", "T (V)": "#c60003"},
        ),
    ]
    columns, names, colors = find_first_existing_column_group(df, column_groups, "tensão")

    fig = px.line(df, x="Datetime", y=columns, labels={"value": "Tensão (V)", "variable": "LEGENDA:"})
    fig.data = []
    for col, name in zip(columns, names):
        fig.add_trace(
            go.Scatter(
                x=df["Datetime"],
                y=df[col],
                mode="lines",
                name=name,
                line=dict(color=colors[name], width=1),
            )
        )

    y_max_value, y_min_value, x_max, x_min = _get_extreme_points(df, columns)

    if x_max is not None:
        add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_max,
            y_value=y_max_value,
            text=f"{y_max_value:.2f} V".replace(".", ","),
            name="Máx (V)",
            color="black",
            kind="max",
        )
    if x_min is not None:
        add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_min,
            y_value=y_min_value,
            text=f"{y_min_value:.2f} V".replace(".", ","),
            name="Mín (V)",
            color="grey",
            kind="min",
        )

    min_adequacy, max_adequacy, min_critical, max_critical = get_tension_limits(processed.tension)
    full = is_full_view(initial_view)

    if full:
        fig.add_hline(
            y=min_adequacy,
            line_dash="dash",
            line_color="orange",
            annotation_text=f"≥{min_adequacy}V ADEQUADA",
            annotation_position="top right",
            annotation_bgcolor="white",
            annotation_font=dict(family="Arial", size=10),
            annotation_yshift=1,
        )
        fig.add_hline(
            y=max_adequacy,
            line_dash="dash",
            line_color="orange",
            annotation_text=f"≤{max_adequacy}V ADEQUADA",
            annotation_position="bottom right",
            annotation_bgcolor="white",
            annotation_font=dict(family="Arial", size=10),
            annotation_yshift=-1,
        )
        if y_max_value > max_adequacy:
            y_axis_range = None
        else:
            y_axis_range = [min_adequacy * 0.99, max_adequacy * 1.01]
    else:
        if y_max_value > max_adequacy or y_min_value < min_adequacy:
            fig.add_hline(
                y=min_adequacy,
                line_dash="dash",
                line_color="orange",
                annotation_text=f"≥{min_adequacy}V ADEQUADA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
            fig.add_hline(
                y=max_adequacy,
                line_dash="dash",
                line_color="orange",
                annotation_text=f"≤{max_adequacy}V ADEQUADA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )
        y_axis_range = None

    if processed.tension == "220":
        if y_max_value > 231 or y_min_value < 202:
            fig.add_hline(
                y=202,
                line_dash="dash",
                line_color="orange",
                annotation_text="≥202V ADEQUADA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
            fig.add_hline(
                y=231,
                line_dash="dash",
                line_color="orange",
                annotation_text="≤231V ADEQUADA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )
            fig.add_hline(
                y=202,
                line_dash="dash",
                line_color="rgba(0,0,0,0)",
                annotation_text="<202V PRECÁRIA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )
            fig.add_hline(
                y=231,
                line_dash="dash",
                line_color="rgba(0,0,0,0)",
                annotation_text=">231V PRECÁRIA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        if y_max_value > 233:
            fig.add_hline(
                y=233,
                line_dash="dash",
                line_color="red",
                annotation_text=">233V CRÍTICA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        if y_min_value < 191:
            fig.add_hline(
                y=191,
                line_dash="dash",
                line_color="red",
                annotation_text="<191V CRÍTICA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )

    elif processed.tension == "380":
        if y_max_value > 399 or y_min_value < 350:
            fig.add_hline(
                y=350,
                line_dash="dash",
                line_color="orange",
                annotation_text="≥350V ADEQUADA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
            fig.add_hline(
                y=399,
                line_dash="dash",
                line_color="orange",
                annotation_text="≤399V ADEQUADA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )
            fig.add_hline(
                y=350,
                line_dash="dash",
                line_color="rgba(0,0,0,0)",
                annotation_text="<350V PRECÁRIA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )
            fig.add_hline(
                y=399,
                line_dash="dash",
                line_color="rgba(0,0,0,0)",
                annotation_text=">399V PRECÁRIA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        if y_max_value > 403:
            fig.add_hline(
                y=403,
                line_dash="dash",
                line_color="red",
                annotation_text=">403V CRÍTICA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        if y_min_value < 331:
            fig.add_hline(
                y=331,
                line_dash="dash",
                line_color="red",
                annotation_text="<331V CRÍTICA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )

    elif processed.tension == "254":
        if y_max_value > 267 or y_min_value < 234:
            fig.add_hline(
                y=234,
                line_dash="dash",
                line_color="orange",
                annotation_text="≥234V ADEQUADA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
            fig.add_hline(
                y=267,
                line_dash="dash",
                line_color="orange",
                annotation_text="≤267V ADEQUADA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )
            fig.add_hline(
                y=234,
                line_dash="dash",
                line_color="rgba(0,0,0,0)",
                annotation_text="<234V PRECÁRIA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )
            fig.add_hline(
                y=267,
                line_dash="dash",
                line_color="rgba(0,0,0,0)",
                annotation_text=">267V PRECÁRIA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        if y_max_value > 269:
            fig.add_hline(
                y=269,
                line_dash="dash",
                line_color="red",
                annotation_text=">269V CRÍTICA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        if y_min_value < 221:
            fig.add_hline(
                y=221,
                line_dash="dash",
                line_color="red",
                annotation_text="<221V CRÍTICA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )

    elif processed.tension == "440":
        if y_max_value > 462 or y_min_value < 405:
            fig.add_hline(
                y=405,
                line_dash="dash",
                line_color="orange",
                annotation_text="≥405V ADEQUADA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
            fig.add_hline(
                y=462,
                line_dash="dash",
                line_color="orange",
                annotation_text="≤462V ADEQUADA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )
            fig.add_hline(
                y=405,
                line_dash="dash",
                line_color="rgba(0,0,0,0)",
                annotation_text="<405V PRECÁRIA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )
            fig.add_hline(
                y=462,
                line_dash="dash",
                line_color="rgba(0,0,0,0)",
                annotation_text=">462V PRECÁRIA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        if y_max_value > 466:
            fig.add_hline(
                y=466,
                line_dash="dash",
                line_color="red",
                annotation_text=">466V CRÍTICA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        if y_min_value < 383:
            fig.add_hline(
                y=383,
                line_dash="dash",
                line_color="red",
                annotation_text="<383V CRÍTICA",
                annotation_position="bottom right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=-1,
            )

    fig = apply_common_layout(fig, df, show_logo=show_logo)
    fig.update_layout(
        yaxis=dict(
            gridcolor="grey",
            zerolinecolor="grey",
            tickmode="auto",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            dtick=1,
            title_text="TENSÃO (V)",
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
            range=y_axis_range,
        ),
        title={
            "text": (
                f"<b>GRÁFICO TENSÃO - {processed.company} - {processed.city}</b><br>"
                f"<sub><b>{processed.local} - TRANSFORMADOR {processed.trafo}kVA - "
                f"{processed.tension}V - INT: {processed.integration_time}s - REV{processed.revision}</b></sub><br>"
                f"<sub>FAIXA ADEQUADA {min_adequacy} ≤ TL ≤ {max_adequacy} - ANEEL PRODIST MÓDULO 8</sub>"
            ),
            "y": 0.98, "x": 0.5, "xanchor": "center", "yanchor": "top",
            "font": {"family": "Arial", "size": 15, "color": "#000000"},
        },
    )
    return fig


def create_current_graph(
    processed: ProcessedData,
    show_logo: bool = False,
    initial_view: bool | None = None,
) -> go.Figure:
    df = processed.dataframe.copy()
    columns = ["Corrente A (médio)(A)", "Corrente B (médio)(A)", "Corrente C (médio)(A)"]
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"Colunas de corrente não encontradas: {missing}")

    fig = px.line(df, x="Datetime", y=columns, labels={"value": "Corrente (A)", "variable": "LEGENDA:"})
    names = ["R (A)", "S (A)", "T (A)"]
    colors = {"R (A)": "#77c1f9", "S (A)": "#52c458", "T (A)": "#ff3616"}

    fig.data = []
    for col, name in zip(columns, names):
        fig.add_trace(
            go.Scatter(
                x=df["Datetime"],
                y=df[col],
                mode="lines",
                name=name,
                line=dict(color=colors[name], width=1),
            )
        )

    y_max_value, y_min_value, x_max, x_min = _get_extreme_points(df, columns)

    max_current = (processed.trafo * 1000) / (float(processed.tension) * math.sqrt(3))
    full = is_full_view(initial_view)

    if full:
        fig.add_hline(
            y=max_current,
            line_dash="dash",
            line_color="red",
            annotation_text=f"CORRENTE NOMINAL= {max_current:.2f}A",
            annotation_position="top right",
            annotation_bgcolor="white",
            annotation_font=dict(family="Arial", size=10),
            annotation_yshift=1,
        )
        y_axis_range = None if y_max_value > max_current else [0, max_current * 1.01]
    else:
        if y_max_value > max_current:
            fig.add_hline(
                y=max_current,
                line_dash="dash",
                line_color="red",
                annotation_text=f"CORRENTE NOMINAL= {max_current:.2f}A",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        y_axis_range = None

    if x_max is not None:
        add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_max,
            y_value=y_max_value,
            text=f"{y_max_value:.2f} A".replace(".", ","),
            name="Máx (A)",
            color="black",
            kind="max",
        )
    if x_min is not None:
        min_text_position = get_safe_text_position(x_min, y_min_value, df, y_min_value, y_max_value, "min")
        add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_min,
            y_value=y_min_value,
            text=f"{y_min_value:.2f} A".replace(".", ","),
            name="Mín (A)",
            color="grey",
            kind="min",
        )

    fig = apply_common_layout(fig, df, show_logo=show_logo)
    fig.update_layout(
        yaxis=dict(
            gridcolor="grey",
            zerolinecolor="grey",
            tickmode="auto",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            dtick=1,
            title_text="CORRENTE (A)",
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
            range=y_axis_range,
        ),
        title={
            "text": (
                f"<b>GRÁFICO CORRENTE - {processed.company} - {processed.city}</b><br>"
                f"<sub>{processed.local} - TRANSFORMADOR {processed.trafo}kVA - "
                f"{processed.tension}V - INT: {processed.integration_time}s - REV{processed.revision}</sub>"
            ),
            "y": 0.98, "x": 0.5, "xanchor": "center", "yanchor": "top",
            "font": {"family": "Arial", "size": 15, "color": "#000000"},
        },
    )
    return fig


def create_active_power_graph(
    processed: ProcessedData,
    show_logo: bool = False,
    initial_view: bool | None = None,
) -> go.Figure:
    df = processed.dataframe.copy()
    column = find_first_existing_column(
        df,
        [
            "Pot Ativa Cons. Trifásica Cons. (médio)(kW)",
            "Potência Ativa Trifásica (médio)(kW)",
        ],
        "potência ativa",
    )

    fig = px.line(df, x="Datetime", y=[column], labels={"value": "Potência Ativa (kW)", "variable": "LEGENDA:"})
    fig.data = []
    fig.add_trace(
        go.Scatter(
            x=df["Datetime"],
            y=df[column],
            mode="lines",
            name="kW 3F",
            line=dict(color="#166cc2", width=1),
        )
    )

    max_val = df[column].max()
    min_val = df[column].min()
    y_max_value = max_val
    x_max = df.loc[df[column].idxmax(), "Datetime"]
    x_min = df.loc[df[column].idxmin(), "Datetime"]

    add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_max,
            y_value=max_val,
            text=f"{max_val:.2f} kW".replace(".", ","),
            name="Máx (kW)",
            color="black",
            kind="max",
        )
    min_text_position = get_safe_text_position(x_min, min_val, df, min_val, max_val, "min")
    add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_min,
            y_value=min_val,
            text=f"{min_val:.2f} kW".replace(".", ","),
            name="Mín (kW)",
            color="grey",
            kind="min",
        )

    max_active_power = processed.trafo
    full = is_full_view(initial_view)
    if full:
        fig.add_hline(
            y=max_active_power,
            line_dash="dash",
            line_color="red",
            annotation_text=f"POT. NOMINAL {max_active_power:.1f}kW",
            annotation_position="top right",
            annotation_bgcolor="white",
            annotation_font=dict(family="Arial", size=10),
            annotation_yshift=1,
        )
        y_axis_range = None if y_max_value > max_active_power else [0, max_active_power * 1.01]
    else:
        if y_max_value > max_active_power:
            fig.add_hline(
                y=max_active_power,
                line_dash="dash",
                line_color="red",
                annotation_text=f"POT. NOMINAL {max_active_power:.1f}kW",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        y_axis_range = None

    fig = apply_common_layout(fig, df, show_logo=show_logo)
    fig.update_layout(
        yaxis=dict(
            gridcolor="grey",
            zerolinecolor="grey",
            tickmode="auto",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            dtick=1,
            title_text="POTÊNCIA ATIVA (kW)",
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
            range=y_axis_range,
        ),
        title={
            "text": (
                f"<b>GRÁFICO POTÊNCIA ATIVA - {processed.company} - {processed.city}</b><br>"
                f"<sub>{processed.local} - TRANSFORMADOR {processed.trafo}kVA - "
                f"{processed.tension}V - INT: {processed.integration_time}s - REV{processed.revision}</sub>"
            ),
            "y": 0.98, "x": 0.5, "xanchor": "center", "yanchor": "top",
            "font": {"family": "Arial", "size": 15, "color": "#000000"},
        },
    )
    return fig


def create_apparent_power_graph(
    processed: ProcessedData,
    show_logo: bool = False,
    initial_view: bool | None = None,
) -> go.Figure:
    df = processed.dataframe.copy()
    column = find_first_existing_column(
        df,
        [
            "Pot Aparente Trifásica (médio)(kVA)",
            "Potência Aparente Trifásica (médio)(kVA)",
        ],
        "potência aparente",
    )

    fig = px.line(df, x="Datetime", y=[column], labels={"value": "Potência Aparente (kVA)", "variable": "LEGENDA:"})
    fig.data = []
    fig.add_trace(
        go.Scatter(
            x=df["Datetime"],
            y=df[column],
            mode="lines",
            name="kVA 3F",
            line=dict(color="#77c1f9", width=1),
        )
    )

    max_val = df[column].max()
    min_val = df[column].min()
    y_max_value = max_val
    x_max = df.loc[df[column].idxmax(), "Datetime"]
    x_min = df.loc[df[column].idxmin(), "Datetime"]

    add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_max,
            y_value=max_val,
            text=f"{max_val:.2f} kVA".replace(".", ","),
            name="Máx (kVA)",
            color="black",
            kind="max",
        )
    min_text_position = get_safe_text_position(x_min, min_val, df, min_val, max_val, "min")
    add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_min,
            y_value=min_val,
            text=f"{min_val:.2f} kVA".replace(".", ","),
            name="Mín (kVA)",
            color="grey",
            kind="min",
        )

    max_apparent_power = processed.trafo
    full = is_full_view(initial_view)
    if full:
        fig.add_hline(
            y=max_apparent_power,
            line_dash="dash",
            line_color="red",
            annotation_text=f"POT. NOMINAL {max_apparent_power:.1f}kVA",
            annotation_position="top right",
            annotation_bgcolor="white",
            annotation_font=dict(family="Arial", size=10),
            annotation_yshift=1,
        )
        y_axis_range = None if y_max_value > max_apparent_power else [0, max_apparent_power * 1.01]
    else:
        if y_max_value > max_apparent_power:
            fig.add_hline(
                y=max_apparent_power,
                line_dash="dash",
                line_color="red",
                annotation_text=f"POT. NOMINAL {max_apparent_power:.1f}kVA",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        y_axis_range = None

    fig = apply_common_layout(fig, df, show_logo=show_logo)
    fig.update_layout(
        yaxis=dict(
            gridcolor="grey",
            zerolinecolor="grey",
            tickmode="auto",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            dtick=1,
            title_text="POTÊNCIA APARENTE (kVA)",
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
            range=y_axis_range,
        ),
        title={
            "text": (
                f"<b>GRÁFICO POTÊNCIA APARENTE - {processed.company} - {processed.city}</b><br>"
                f"<sub>{processed.local} - TRANSFORMADOR {processed.trafo}kVA - "
                f"{processed.tension}V - INT: {processed.integration_time}s - REV{processed.revision}</sub>"
            ),
            "y": 0.98, "x": 0.5, "xanchor": "center", "yanchor": "top",
            "font": {"family": "Arial", "size": 15, "color": "#000000"},
        },
    )
    return fig


def create_pf_graph(processed: ProcessedData, show_logo: bool = False) -> go.Figure:
    """
    Cria o gráfico de fator de potência.

    Otimizações aplicadas:
    - removido px.line() inicial desnecessário;
    - cálculo do FP ajustado vetorizado, sem apply linha a linha;
    - identificação dos períodos 00:00–06:00 vetorizada, sem loop por registro.
    """
    df = processed.dataframe.copy()
    column = find_first_existing_column(df, ["FP Trifásico (médio)(%)"], "fator de potência")

    adjusted_column = "Adjusted PF"
    fp_values = pd.to_numeric(df[column], errors="coerce").fillna(0)
    df[adjusted_column] = 0.0

    positive_mask = fp_values > 0
    df.loc[positive_mask, adjusted_column] = (fp_values.loc[positive_mask] - 100) * -1
    df.loc[~positive_mask, adjusted_column] = (fp_values.loc[~positive_mask] + 100) * -1

    fig = go.Figure()

    # Faixas cinzas do horário capacitivo: 00:00 até antes de 06:00.
    # Antes era feito com loop linha a linha; agora identifica os blocos por diferença de tempo.
    hour_mask = (df["Datetime"].dt.hour >= 0) & (df["Datetime"].dt.hour < 6)
    if hour_mask.any():
        capacitive_times = df.loc[hour_mask, "Datetime"].sort_values().reset_index(drop=True)

        if len(capacitive_times) > 0:
            time_diffs = capacitive_times.diff().dt.total_seconds().fillna(0)
            segment_id = (time_diffs > 3600).cumsum()

            segments = capacitive_times.groupby(segment_id).agg(["first", "last"])

            for _, row in segments.iterrows():
                fig.add_vrect(
                    x0=row["first"],
                    x1=row["last"],
                    fillcolor="gray",
                    opacity=0.2,
                    layer="below",
                    line_width=0,
                )

    fig.add_trace(
        go.Scatter(
            x=df["Datetime"],
            y=df[adjusted_column],
            mode="lines",
            name="FP (%)",
            line=dict(color="#166cc2", width=1),
        )
    )

    fig.add_hline(
        y=8,
        line_dash="dash",
        line_color="red",
        annotation_text="92 L",
        annotation_position="top right",
        annotation_bgcolor="white",
        annotation_font=dict(family="Arial", size=10),
        annotation_yshift=1,
    )
    fig.add_hline(
        y=-8,
        line_dash="dash",
        line_color="red",
        annotation_text="92 C",
        annotation_position="bottom right",
        annotation_bgcolor="white",
        annotation_font=dict(family="Arial", size=10),
        annotation_yshift=-1,
    )

    max_val = df[adjusted_column].max()
    min_val = df[adjusted_column].min()
    x_max = df.loc[df[adjusted_column].idxmax(), "Datetime"]
    x_min = df.loc[df[adjusted_column].idxmin(), "Datetime"]

    max_text = f"{100 - abs(max_val):.2f}" + (" L" if max_val > 0 else " C")
    min_text = f"{100 - abs(min_val):.2f}" + (" L" if min_val > 0 else " C")

    add_extreme_marker(
        fig=fig,
        df=df,
        x_value=x_max,
        y_value=max_val,
        text=max_text.replace(".", ","),
        name="Máx",
        color="black",
        kind="max",
    )
    add_extreme_marker(
        fig=fig,
        df=df,
        x_value=x_min,
        y_value=min_val,
        text=min_text.replace(".", ","),
        name="Mín",
        color="grey",
        kind="min",
    )

    fig = apply_common_layout(fig, df, show_logo=show_logo)
    fig.update_layout(
        yaxis=dict(
            gridcolor="grey",
            zerolinecolor="grey",
            range=[-101, 101],
            tickmode="array",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            tickvals=list(range(-100, 101, 10)),
            ticktext=[
                "100" if x == 0 else f'{abs(100 - abs(x))} {"C" if x < 0 else "L"}'
                for x in range(-100, 101, 10)
            ],
        ),
        title={
            "text": (
                f"<b>GRÁFICO FATOR DE POTÊNCIA - {processed.company} - {processed.city}</b><br>"
                f"<sub>{processed.local} - TRANSFORMADOR {processed.trafo}kVA - "
                f"{processed.tension}V - INT: {processed.integration_time}s - REV{processed.revision}</sub>"
            ),
            "y": 0.98, "x": 0.5, "xanchor": "center", "yanchor": "top",
            "font": {"family": "Arial", "size": 15, "color": "#000000"},
        },
    )

    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color="rgb(210, 210, 210)", width=10),
            showlegend=True,
            name="H. Cap.",
            hoverinfo="none",
        )
    )
    return fig

def create_tension_imbalance_graph(
    processed: ProcessedData,
    show_logo: bool = False,
    initial_view: bool | None = None,
) -> go.Figure:
    df = processed.dataframe.copy()
    column = find_first_existing_column(df, ["Deseq. Tensão (médio)(%)"], "desequilíbrio de tensão")

    fig = px.line(df, x="Datetime", y=[column], labels={"value": "Desequilíbrio de Tensão (%)", "variable": "LEGENDA:"})
    fig.data = []
    fig.add_trace(
        go.Scatter(
            x=df["Datetime"],
            y=df[column],
            mode="lines",
            name="%",
            line=dict(color="#166cc2", width=1),
        )
    )

    max_val = df[column].max()
    min_val = df[column].min()
    y_max_value = max_val
    x_max = df.loc[df[column].idxmax(), "Datetime"]
    x_min = df.loc[df[column].idxmin(), "Datetime"]

    add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_max,
            y_value=max_val,
            text=f"{max_val:.2f} %".replace(".", ","),
            name="Máx (%)",
            color="black",
            kind="max",
        )
    min_text_position = get_safe_text_position(x_min, min_val, df, min_val, max_val, "min")
    add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_min,
            y_value=min_val,
            text=f"{min_val:.2f} %".replace(".", ","),
            name="Mín (%)",
            color="grey",
            kind="min",
        )

    max_tension_imbalance = 3
    full = is_full_view(initial_view)
    if full:
        fig.add_hline(
            y=max_tension_imbalance,
            line_dash="dash",
            line_color="red",
            annotation_text="LIMITE = 3%",
            annotation_position="top right",
            annotation_bgcolor="white",
            annotation_font=dict(family="Arial", size=10),
            annotation_yshift=1,
        )
        y_axis_range = None if y_max_value >= max_tension_imbalance else [0, max_tension_imbalance * 1.01]
    else:
        if y_max_value >= max_tension_imbalance:
            fig.add_hline(
                y=max_tension_imbalance,
                line_dash="dash",
                line_color="red",
                annotation_text="LIMITE = 3%",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        y_axis_range = None

    fig = apply_common_layout(fig, df, show_logo=show_logo)
    fig.update_layout(
        yaxis=dict(
            gridcolor="grey",
            zerolinecolor="grey",
            tickmode="auto",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            dtick=1,
            title_text="DESEQUILÍBRIO DE TENSÃO (%)",
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
            range=y_axis_range,
        ),
        title={
            "text": (
                f"<b>GRÁFICO DESEQUILÍBRIO DE TENSÃO - {processed.company} - {processed.city}</b><br>"
                f"<sub><b>{processed.local} - TRANSFORMADOR {processed.trafo}kVA - "
                f"{processed.tension}V - INT: {processed.integration_time}s - REV{processed.revision}</b></sub><br>"
                f"<sub>LIMITE 3% - ANEEL PRODIST MÓDULO 8</sub>"
            ),
            "y": 0.98, "x": 0.5, "xanchor": "center", "yanchor": "top",
            "font": {"family": "Arial", "size": 15, "color": "#000000"},
        },
    )
    return fig


def create_current_imbalance_graph(processed: ProcessedData, show_logo: bool = False) -> go.Figure:
    df = processed.dataframe.copy()
    column = find_first_existing_column(df, ["Deseq. Corrente (médio)(%)"], "desequilíbrio de corrente")

    fig = px.line(df, x="Datetime", y=[column], labels={"value": "Desequilíbrio de Corrente (%)", "variable": "LEGENDA:"})
    fig.data = []
    fig.add_trace(
        go.Scatter(
            x=df["Datetime"],
            y=df[column],
            mode="lines",
            name="%",
            line=dict(color="#166cc2", width=1),
        )
    )

    max_val = df[column].max()
    min_val = df[column].min()
    x_max = df.loc[df[column].idxmax(), "Datetime"]
    x_min = df.loc[df[column].idxmin(), "Datetime"]

    add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_max,
            y_value=max_val,
            text=f"{max_val:.2f} %".replace(".", ","),
            name="Máx (%)",
            color="black",
            kind="max",
        )
    add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_min,
            y_value=min_val,
            text=f"{min_val:.2f} %".replace(".", ","),
            name="Mín (%)",
            color="grey",
            kind="min",
        )

    fig = apply_common_layout(fig, df, show_logo=show_logo)
    fig.update_layout(
        yaxis=dict(
            gridcolor="grey",
            zerolinecolor="grey",
            tickmode="auto",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            dtick=1,
            title_text="DESEQUILÍBRIO DE CORRENTE (%)",
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
        ),
        title={
            "text": (
                f"<b>GRÁFICO DESEQUILÍBRIO DE CORRENTE - {processed.company} - {processed.city}</b><br>"
                f"<sub>{processed.local} - TRANSFORMADOR {processed.trafo}kVA - "
                f"{processed.tension}V - INT: {processed.integration_time}s - REV{processed.revision}</sub>"
            ),
            "y": 0.98, "x": 0.5, "xanchor": "center", "yanchor": "top",
            "font": {"family": "Arial", "size": 15, "color": "#000000"},
        },
    )
    return fig


def create_dht_voltage_graph(
    processed: ProcessedData,
    show_logo: bool = False,
    initial_view: bool | None = None,
) -> go.Figure:
    df = processed.dataframe.copy()
    columns = ["DHT VA (médio)(%)", "DHT VB (médio)(%)", "DHT VC (médio)(%)"]
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"Colunas de DHT tensão não encontradas: {missing}")

    fig = px.line(df, x="Datetime", y=columns, labels={"value": "DHT Tensão (%)", "variable": "LEGENDA:"})
    names = ["R (%)", "S (%)", "T (%)"]
    colors = {"R (%)": "#166cc2", "S (%)": "#006c17", "T (%)": "#c60003"}

    fig.data = []
    for col, name in zip(columns, names):
        fig.add_trace(
            go.Scatter(
                x=df["Datetime"],
                y=df[col],
                mode="lines",
                name=name,
                line=dict(color=colors[name], width=1),
            )
        )

    y_max_value, y_min_value, x_max, x_min = _get_extreme_points(df, columns)

    if x_max is not None:
        add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_max,
            y_value=y_max_value,
            text=f"{y_max_value:.2f} %".replace(".", ","),
            name="Máx",
            color="black",
            kind="max",
        )
    if x_min is not None:
        add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_min,
            y_value=y_min_value,
            text=f"{y_min_value:.2f} %".replace(".", ","),
            name="Mín",
            color="grey",
            kind="min",
        )

    max_dht_voltage = 10
    full = is_full_view(initial_view)
    if full:
        fig.add_hline(
            y=max_dht_voltage,
            line_dash="dash",
            line_color="red",
            annotation_text="LIMITE = 10%",
            annotation_position="top right",
            annotation_bgcolor="white",
            annotation_font=dict(family="Arial", size=10),
            annotation_yshift=1,
        )
        y_axis_range = None if y_max_value >= max_dht_voltage else [0, max_dht_voltage * 1.01]
    else:
        if y_max_value >= max_dht_voltage:
            fig.add_hline(
                y=max_dht_voltage,
                line_dash="dash",
                line_color="red",
                annotation_text="LIMITE = 10%",
                annotation_position="top right",
                annotation_bgcolor="white",
                annotation_font=dict(family="Arial", size=10),
                annotation_yshift=1,
            )
        y_axis_range = None

    fig = apply_common_layout(fig, df, show_logo=show_logo)
    fig.update_layout(
        yaxis=dict(
            gridcolor="grey",
            zerolinecolor="grey",
            tickmode="auto",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            dtick=1,
            title_text="DHT TENSÃO (%)",
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
            range=y_axis_range,
        ),
        title={
            "text": (
                f"<b>GRÁFICO DHT TENSÃO - {processed.company} - {processed.city}</b><br>"
                f"<sub><b>{processed.local} - TRANSFORMADOR {processed.trafo}kVA - "
                f"{processed.tension}V - INT: {processed.integration_time}s - REV{processed.revision}</b></sub><br>"
                f"<sub>LIMITE 10% - ANEEL PRODIST MÓDULO 8</sub>"
            ),
            "y": 0.98, "x": 0.5, "xanchor": "center", "yanchor": "top",
            "font": {"family": "Arial", "size": 15, "color": "#000000"},
        },
    )
    return fig


def create_dht_current_graph(processed: ProcessedData, show_logo: bool = False) -> go.Figure:
    df = processed.dataframe.copy()
    columns = ["DHT IA (médio)(%)", "DHT IB (médio)(%)", "DHT IC (médio)(%)"]
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"Colunas de DHT corrente não encontradas: {missing}")

    fig = px.line(df, x="Datetime", y=columns, labels={"value": "DHT Corrente (%)", "variable": "LEGENDA:"})
    names = ["R (%)", "S (%)", "T (%)"]
    colors = {"R (%)": "#166cc2", "S (%)": "#006c17", "T (%)": "#c60003"}

    fig.data = []
    for col, name in zip(columns, names):
        fig.add_trace(
            go.Scatter(
                x=df["Datetime"],
                y=df[col],
                mode="lines",
                name=name,
                line=dict(color=colors[name], width=1),
            )
        )

    y_max_value, y_min_value, x_max, x_min = _get_extreme_points(df, columns)

    if x_max is not None:
        add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_max,
            y_value=y_max_value,
            text=f"{y_max_value:.2f} %".replace(".", ","),
            name="Máx",
            color="black",
            kind="max",
        )
    if x_min is not None:
        add_extreme_marker(
            fig=fig,
            df=df,
            x_value=x_min,
            y_value=y_min_value,
            text=f"{y_min_value:.2f} %".replace(".", ","),
            name="Mín",
            color="grey",
            kind="min",
        )

    fig = apply_common_layout(fig, df, show_logo=show_logo)
    fig.update_layout(
        yaxis=dict(
            gridcolor="grey",
            zerolinecolor="grey",
            tickmode="auto",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            dtick=1,
            title_text="DHT CORRENTE (%)",
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
        ),
        title={
            "text": (
                f"<b>GRÁFICO DHT CORRENTE - {processed.company} - {processed.city}</b><br>"
                f"<sub>{processed.local} - TRANSFORMADOR {processed.trafo}kVA - "
                f"{processed.tension}V - INT: {processed.integration_time}s - REV{processed.revision}</sub>"
            ),
            "y": 0.98, "x": 0.5, "xanchor": "center", "yanchor": "top",
            "font": {"family": "Arial", "size": 15, "color": "#000000"},
        },
    )
    return fig


def create_combined_vxi_graph(processed: ProcessedData, show_logo: bool = False) -> go.Figure:
    df = processed.dataframe.copy()
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    tension_graph = create_tension_graph(processed, show_logo=show_logo, initial_view=False)
    for trace in tension_graph.data:
        fig.add_trace(trace, secondary_y=False)
    copy_point_annotations(tension_graph, fig, yref="y")

    current_graph = create_current_graph(processed, show_logo=show_logo, initial_view=False)
    for trace in current_graph.data:
        fig.add_trace(trace, secondary_y=True)
    copy_point_annotations(current_graph, fig, yref="y2")

    fig = apply_common_layout(fig, df, show_logo=show_logo)
    fig.update_layout(
        yaxis=dict(
            title_text="TENSÃO (V)",
            gridcolor="grey",
            zerolinecolor="grey",
            tickmode="auto",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            dtick=1,
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
        ),
        yaxis2=dict(
            title_text="CORRENTE (A)",
            tickmode="auto",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            dtick=1,
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
        ),
        title={
            "text": (
                f"<b>GRÁFICO TENSÃO & CORRENTE - {processed.company} - {processed.city}</b><br>"
                f"<sub>{processed.local} - TRANSFORMADOR {processed.trafo}kVA - "
                f"{processed.tension}V - INT: {processed.integration_time}s - REV{processed.revision}</sub>"
            ),
            "y": 0.98, "x": 0.5, "xanchor": "center", "yanchor": "top",
            "font": {"family": "Arial", "size": 15, "color": "#000000"},
        },
        legend_title_text="LEGENDA:",
    )
    return fig


def create_combined_kwxkva_graph(processed: ProcessedData, show_logo: bool = False) -> go.Figure:
    df = processed.dataframe.copy()
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    active_power_graph = create_active_power_graph(processed, show_logo=show_logo, initial_view=False)
    for trace in active_power_graph.data:
        fig.add_trace(trace, secondary_y=False)
    copy_point_annotations(active_power_graph, fig, yref="y")

    apparent_power_graph = create_apparent_power_graph(processed, show_logo=show_logo, initial_view=False)
    for trace in apparent_power_graph.data:
        fig.add_trace(trace, secondary_y=True)
    copy_point_annotations(apparent_power_graph, fig, yref="y2")

    fig = apply_common_layout(fig, df, show_logo=show_logo)
    fig.update_layout(
        yaxis=dict(
            title_text="POTÊNCIA ATIVA (kW)",
            gridcolor="grey",
            zeroline=True,
            zerolinecolor="grey",
            tickmode="auto",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            dtick=1,
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
            showgrid=True,
        ),
        yaxis2=dict(
            title_text="POTÊNCIA APARENTE (kVA)",
            tickmode="auto",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            dtick=1,
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
            showgrid=False,
        ),
        title={
            "text": (
                f"<b>GRÁFICO POT. ATIVA & POT. APARENTE - {processed.company} - {processed.city}</b><br>"
                f"<sub>{processed.local} - TRANSFORMADOR {processed.trafo}kVA - "
                f"{processed.tension}V - INT: {processed.integration_time}s - REV{processed.revision}</sub>"
            ),
            "y": 0.98, "x": 0.5, "xanchor": "center", "yanchor": "top",
            "font": {"family": "Arial", "size": 15, "color": "#000000"},
        },
        legend_title_text="LEGENDA:",
    )
    return fig

def _build_consumption_series(df: pd.DataFrame, integration_time: int | float | None = None) -> pd.Series:
    """
    Retorna consumo incremental em kWh por registro.

    Prioridade:
    1. Usa energia trifásica consumida quando a coluna existir e possuir valores válidos > 0.
    2. Caso contrário, calcula por potência ativa trifásica e intervalo de integração.
    """
    energy_candidates = [
        "Energia TRI Cons. (médio)((Kwh))",
        "Energia TRI Cons. (médio)(kWh)",
        "Energia Trifásica Cons. (médio)(kWh)",
        "Energia TRI Cons.",
    ]

    for column in energy_candidates:
        if column in df.columns:
            energy = pd.to_numeric(df[column], errors="coerce").fillna(0)
            if energy.abs().sum() > 0:
                return energy.clip(lower=0)

    power_column = find_first_existing_column(
        df,
        [
            "Pot Ativa Cons. Trifásica Cons. (médio)(kW)",
            "Potência Ativa Trifásica (médio)(kW)",
        ],
        "potência ativa para cálculo de consumo",
    )

    power_kw = pd.to_numeric(df[power_column], errors="coerce").fillna(0).clip(lower=0)

    if integration_time and integration_time > 0:
        seconds = float(integration_time)
    else:
        datetimes = pd.to_datetime(df["Datetime"], errors="coerce").sort_values()
        diffs = datetimes.diff().dt.total_seconds().dropna()
        diffs = diffs[diffs > 0]
        seconds = float(diffs.median()) if not diffs.empty else 0.0

    if seconds <= 0:
        return pd.Series(0.0, index=df.index)

    return power_kw * (seconds / 3600.0)


def create_consumption_graph(
    processed: ProcessedData,
    show_logo: bool = False,
    initial_view: bool | None = None,
) -> go.Figure:
    """
    Gráfico de consumo diário de energia ativa em kWh.

    - Dias completos: barra azul.
    - Dias incompletos, com menos de 24h de medição: barra vermelha.
    - Primata: utiliza energia trifásica consumida exportada pelo equipamento.
    - Embrasul: calcula por P(kW) x intervalo(h), quando energia não estiver disponível.
    """
    df = processed.dataframe.copy()

    if df.empty:
        raise ValueError("DataFrame vazio para geração do gráfico de consumo.")

    df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")
    df = df.dropna(subset=["Datetime"]).copy()

    if df.empty:
        raise ValueError("DataFrame sem registros válidos de data/hora para geração do gráfico de consumo.")

    df["Consumo kWh"] = _build_consumption_series(df, processed.integration_time)

    daily = (
        df.set_index("Datetime")["Consumo kWh"]
        .resample("D")
        .sum()
        .reset_index()
    )
    daily = daily[daily["Consumo kWh"] > 0].copy()

    if daily.empty:
        daily = pd.DataFrame({"Datetime": [df["Datetime"].min()], "Consumo kWh": [0.0]})

    # Identifica dias incompletos: dias com menos de 24h de registros medidos.
    coverage = (
        df.groupby(df["Datetime"].dt.date)["Datetime"]
        .agg(["min", "max"])
        .reset_index()
        .rename(columns={"Datetime": "Date"})
    )

    coverage["horas_medidas"] = (
        coverage["max"] - coverage["min"]
    ).dt.total_seconds() / 3600

    dias_incompletos = set(
        coverage.loc[coverage["horas_medidas"] < 23.9, "Date"]
    )

    daily["Date"] = daily["Datetime"].dt.date
    daily["incompleto"] = daily["Date"].isin(dias_incompletos)
    daily["Data"] = daily["Datetime"].dt.strftime("%d/%m/%Y")
    daily["Label"] = daily["Consumo kWh"].map(lambda value: f"{value:.2f}".replace(".", ","))
    daily["Cor"] = daily["incompleto"].map(lambda inc: "#ed1c24" if inc else "#08245c")

    fig = go.Figure()

    # Barras principais sem item próprio na legenda; a legenda será feita por traços auxiliares.
    fig.add_trace(
        go.Bar(
            x=daily["Datetime"],
            y=daily["Consumo kWh"],
            name="Consumo",
            marker=dict(color=daily["Cor"].tolist()),
            text=daily["Label"],
            textposition="outside",
            textfont=dict(family="Arial", size=11, color="#000000"),
            cliponaxis=False,
            hovertemplate="Data: %{customdata}<br>Consumo: %{y:.2f} kWh<extra></extra>",
            customdata=daily["Data"],
            showlegend=False,
        )
    )

    # Traços auxiliares apenas para legenda.
    fig.add_trace(
        go.Bar(
            x=[None],
            y=[None],
            name="COMPLETO",
            marker=dict(color="#08245c"),
            hoverinfo="skip",
            showlegend=True,
        )
    )
    fig.add_trace(
        go.Bar(
            x=[None],
            y=[None],
            name="INCOMPLETO",
            marker=dict(color="#ed1c24"),
            hoverinfo="skip",
            showlegend=True,
        )
    )

    total_consumption = daily["Consumo kWh"].sum()
    total_text = f"{total_consumption:.2f}".replace(".", ",")

    max_consumption = daily["Consumo kWh"].max()
    y_axis_range = [0, max_consumption * 1.18] if max_consumption > 0 else [0, 1]

    tickvals = daily["Datetime"].tolist()
    ticktext = daily["Datetime"].dt.strftime("%d/%m/%Y").tolist()

    fig = apply_common_layout(fig, df, show_logo=show_logo)
    fig.update_layout(
        bargap=0.65 if len(daily) <= 12 else 0.35,
        xaxis=dict(
            gridcolor="lightgrey",
            zerolinecolor="lightgrey",
            tickangle=270,
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            title_text="",
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
        ),
        yaxis=dict(
            gridcolor="lightgrey",
            zerolinecolor="lightgrey",
            tickfont={"family": "Arial", "size": 11, "color": "#000000"},
            ticklabelstandoff=Y_AXIS_TICK_LABEL_STANDOFF,
            title_text="CONSUMO (kWh)",
            title_font={"family": "Arial", "size": 11, "color": "#000000"},
            range=y_axis_range,
        ),
        title={
            "text": (
                f"<b>GRÁFICO CONSUMO DE ENERGIA - {processed.company} - {processed.city}</b><br>"
                f"<sub>{processed.local} - TRANSFORMADOR {processed.trafo}kVA - "
                f"{processed.tension}V - INT: {processed.integration_time}s - REV{processed.revision}</sub><br>"
                f"<sub><b>TOTAL: {total_text} kWh</b></sub>"
            ),
            "y": 0.98,
            "x": 0.5,
            "xanchor": "center",
            "yanchor": "top",
            "font": {"family": "Arial", "size": 15, "color": "#000000"},
        },
        showlegend=True,
        legend_title_text="LEGENDA:",
        legend=dict(
            x=1.02,
            y=0.98,
            xanchor="left",
            yanchor="top",
            font=dict(family="Arial", size=11, color="#000000"),
            title=dict(font=dict(family="Arial", size=11, color="#000000")),
        ),
    )

    return fig

