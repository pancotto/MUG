from __future__ import annotations

from typing import Any

import pandas as pd


PHASES = ("R", "S", "T")


DEFAULT_PHASE_VISIBILITY = {phase: True for phase in PHASES}


GRAPH_PHASE_TRACE_MAP = {
    "Tensão": {
        "RS (V)": "R",
        "ST (V)": "S",
        "TR (V)": "T",
        "R (V)": "R",
        "S (V)": "S",
        "T (V)": "T",
    },
    "Corrente": {
        "R (A)": "R",
        "S (A)": "S",
        "T (A)": "T",
    },
    "DHT Tensão": {
        "R (%)": "R",
        "S (%)": "S",
        "T (%)": "T",
    },
    "DHT Corrente": {
        "R (%)": "R",
        "S (%)": "S",
        "T (%)": "T",
    },
}


GRAPH_EXTREME_UNITS = {
    "Tensão": "V",
    "Corrente": "A",
    "DHT Tensão": "%",
    "DHT Corrente": "%",
}


def default_phase_visibility() -> dict[str, bool]:
    return DEFAULT_PHASE_VISIBILITY.copy()


def is_phase_sync_graph(graph_name: str) -> bool:
    return graph_name in GRAPH_PHASE_TRACE_MAP


def get_trace_phase(graph_name: str, trace_name: str | None) -> str | None:
    if not trace_name:
        return None

    return GRAPH_PHASE_TRACE_MAP.get(graph_name, {}).get(trace_name)


def get_sync_trace_names(graph_name: str) -> list[str]:
    return list(GRAPH_PHASE_TRACE_MAP.get(graph_name, {}).keys())


def get_phase_label(trace_name: str) -> str:
    return trace_name.split(" (", 1)[0]


def normalize_phase_visibility(phase_visibility: dict[str, bool] | None) -> dict[str, bool]:
    if not phase_visibility:
        return default_phase_visibility()

    normalized = {
        phase: bool(phase_visibility.get(phase, True))
        for phase in PHASES
    }

    if not any(normalized.values()):
        return default_phase_visibility()

    return normalized


def get_phase_trace_updates(
    fig: Any,
    graph_name: str,
    phase_visibility: dict[str, bool] | None,
) -> list[dict[str, object]]:
    visibility = normalize_phase_visibility(phase_visibility)
    updates: list[dict[str, object]] = []

    for index, trace in enumerate(getattr(fig, "data", []) or []):
        phase = get_trace_phase(graph_name, getattr(trace, "name", None))
        if phase is None:
            continue

        visible = visibility.get(phase, True)
        updates.append(
            {
                "index": index,
                "trace": getattr(trace, "name", ""),
                "phase": phase,
                "visible": visible,
            }
        )

    return updates


def apply_phase_visibility_to_figure(
    fig: Any,
    graph_name: str,
    phase_visibility: dict[str, bool] | None,
) -> list[dict[str, object]]:
    updates = get_phase_trace_updates(fig, graph_name, phase_visibility)

    for update in updates:
        trace = fig.data[update["index"]]
        trace.visible = True if update["visible"] else "legendonly"

    return updates


def _is_trace_visible(trace: Any) -> bool:
    return getattr(trace, "visible", True) not in (False, "legendonly")


def _format_extreme_label(value: float, unit: str, phase_label: str) -> str:
    formatted_value = f"{value:.2f}".replace(".", ",")
    return f"{formatted_value} {unit} ({phase_label})"


def _find_extreme_marker_indices(fig: Any) -> tuple[int | None, int | None]:
    max_index = None
    min_index = None

    for index, trace in enumerate(getattr(fig, "data", []) or []):
        name = str(getattr(trace, "name", "") or "").lower()

        if max_index is None and name.startswith(("máx", "max")):
            max_index = index
        elif min_index is None and name.startswith(("mín", "min")):
            min_index = index

    return max_index, min_index


def get_current_extreme_marker_updates(fig: Any) -> list[dict[str, object]]:
    max_index, min_index = _find_extreme_marker_indices(fig)
    updates: list[dict[str, object]] = []

    for index in (max_index, min_index):
        if index is None:
            continue

        trace = fig.data[index]
        x_raw = getattr(trace, "x", None)
        y_raw = getattr(trace, "y", None)
        text_raw = getattr(trace, "text", None)

        updates.append(
            {
                "index": index,
                "x": list(x_raw) if x_raw is not None else [],
                "y": list(y_raw) if y_raw is not None else [],
                "text": list(text_raw) if text_raw is not None else [],
                "hovertemplate": getattr(trace, "hovertemplate", None),
            }
        )

    return updates


def _collect_visible_phase_points(fig: Any, graph_name: str) -> list[dict[str, object]]:
    points: list[dict[str, object]] = []

    for index, trace in enumerate(getattr(fig, "data", []) or []):
        trace_name = getattr(trace, "name", None)
        phase = get_trace_phase(graph_name, trace_name)

        if phase is None or not _is_trace_visible(trace):
            continue

        x_raw = getattr(trace, "x", None)
        y_raw = getattr(trace, "y", None)

        if x_raw is None or y_raw is None:
            continue

        x_values = list(x_raw)
        y_values = pd.to_numeric(pd.Series(y_raw), errors="coerce")

        if y_values.empty:
            continue

        valid_values = y_values.dropna()
        if valid_values.empty:
            continue

        max_position = int(valid_values.idxmax())
        min_position = int(valid_values.idxmin())

        if max_position >= len(x_values) or min_position >= len(x_values):
            continue

        phase_label = get_phase_label(str(trace_name))

        points.append(
            {
                "trace_index": index,
                "trace": trace_name,
                "phase": phase,
                "phase_label": phase_label,
                "max_value": float(y_values.iloc[max_position]),
                "max_x": x_values[max_position],
                "min_value": float(y_values.iloc[min_position]),
                "min_x": x_values[min_position],
            }
        )

    return points


def update_phase_extreme_traces(fig: Any, graph_name: str) -> dict[str, object] | None:
    if graph_name not in GRAPH_EXTREME_UNITS:
        return None

    max_index, min_index = _find_extreme_marker_indices(fig)
    if max_index is None or min_index is None:
        return None

    points = _collect_visible_phase_points(fig, graph_name)
    if not points:
        return None

    unit = GRAPH_EXTREME_UNITS[graph_name]
    max_point = max(points, key=lambda item: item["max_value"])
    min_point = min(points, key=lambda item: item["min_value"])

    max_text = _format_extreme_label(
        value=max_point["max_value"],
        unit=unit,
        phase_label=str(max_point["phase_label"]),
    )
    min_text = _format_extreme_label(
        value=min_point["min_value"],
        unit=unit,
        phase_label=str(min_point["phase_label"]),
    )

    max_trace = fig.data[max_index]
    max_trace.x = [max_point["max_x"]]
    max_trace.y = [max_point["max_value"]]
    max_trace.text = [max_text]
    max_trace.hovertemplate = f"{max_trace.name}: {max_text}<extra></extra>"

    min_trace = fig.data[min_index]
    min_trace.x = [min_point["min_x"]]
    min_trace.y = [min_point["min_value"]]
    min_trace.text = [min_text]
    min_trace.hovertemplate = f"{min_trace.name}: {min_text}<extra></extra>"

    visible_phases = [str(point["phase"]) for point in points]
    result = {
        "graph": graph_name,
        "visible_phases": visible_phases,
        "updates": [
            {
                "index": max_index,
                "x": max_point["max_x"],
                "y": max_point["max_value"],
                "text": max_text,
                "hovertemplate": max_trace.hovertemplate,
            },
            {
                "index": min_index,
                "x": min_point["min_x"],
                "y": min_point["min_value"],
                "text": min_text,
                "hovertemplate": min_trace.hovertemplate,
            },
        ],
        "max": {
            "value": max_point["max_value"],
            "phase": max_point["phase_label"],
        },
        "min": {
            "value": min_point["min_value"],
            "phase": min_point["phase_label"],
        },
    }

    return result
