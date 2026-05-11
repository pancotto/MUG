from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def flatten_metrics(result: dict[str, Any]) -> dict[str, float]:
    flat: dict[str, float] = {}
    metrics = result.get("metrics", {})

    for key in ["startup", "etl", "initial_graph_generation", "zoom_rebuild", "pdf_export"]:
        metric = metrics.get(key)
        if metric and "seconds" in metric:
            flat[f"{key}.seconds"] = float(metric["seconds"])
        if metric and metric.get("memory_delta_mb") is not None:
            flat[f"{key}.memory_delta_mb"] = float(metric["memory_delta_mb"])

    for section_name in ["initial_graphs", "zoom_graphs"]:
        graphs = metrics.get(section_name, {}).get("graphs", {})
        for graph_name, metric in graphs.items():
            flat[f"{section_name}.{graph_name}.seconds"] = float(metric["seconds"])

    pdf_graphs = metrics.get("pdf_graphs", {}).get("graphs", {})
    for graph_name, graph_metrics in pdf_graphs.items():
        for step_name, metric in graph_metrics.items():
            if "seconds" in metric:
                flat[f"pdf_graphs.{graph_name}.{step_name}.seconds"] = float(metric["seconds"])

    return flat


def percent_delta(old: float, new: float) -> float | None:
    if old == 0:
        return None
    return ((new - old) / old) * 100


def format_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1f}%"


def compare(base: dict[str, Any], current: dict[str, Any]) -> str:
    base_metrics = flatten_metrics(base)
    current_metrics = flatten_metrics(current)
    keys = sorted(set(base_metrics) | set(current_metrics))

    lines = [
        "# MUG Benchmark Comparison",
        "",
        f"- Baseline: `{base.get('run_id', 'unknown')}`",
        f"- Current: `{current.get('run_id', 'unknown')}`",
        "",
        "| Metric | Baseline | Current | Delta | Delta % |",
        "|---|---:|---:|---:|---:|",
    ]

    for key in keys:
        base_value = base_metrics.get(key)
        current_value = current_metrics.get(key)

        if base_value is None or current_value is None:
            lines.append(
                f"| {key} | {format_value(base_value)} | {format_value(current_value)} | n/a | n/a |"
            )
            continue

        delta = current_value - base_value
        lines.append(
            f"| {key} | {base_value:.3f} | {current_value:.3f} | {delta:+.3f} | "
            f"{format_percent(percent_delta(base_value, current_value))} |"
        )

    return "\n".join(lines)


def format_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two MUG benchmark JSON files.")
    parser.add_argument("baseline", help="Baseline benchmark JSON.")
    parser.add_argument("current", help="Current benchmark JSON.")
    parser.add_argument("--output", help="Optional Markdown output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    baseline = load_json(args.baseline)
    current = load_json(args.current)
    markdown = compare(baseline, current)

    if args.output:
        Path(args.output).write_text(markdown + "\n", encoding="utf-8")

    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
