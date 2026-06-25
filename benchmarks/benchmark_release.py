from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None

from core.excel_reader import process_input_data
from core.graph_builder import (
    create_active_power_graph,
    create_apparent_power_graph,
    create_combined_kwxkva_graph,
    create_combined_vxi_graph,
    create_consumption_graph,
    create_current_graph,
    create_current_imbalance_graph,
    create_dht_current_graph,
    create_dht_voltage_graph,
    create_pf_graph,
    create_tension_graph,
    create_tension_imbalance_graph,
)
from core.models import EQUIPMENT_TYPE_TRAFO, InputData, ProcessedData
from core.pdf_exporter import (
    GRAPH_EXPORT_ORDER,
    build_custom_pdf_filename,
    build_daily_pdf_filename,
    ensure_unique_pdf_path,
    export_figures_to_pdf,
)
from core.time_filter import (
    apply_time_filter,
    custom_time_filter,
    detect_measurement_days,
    get_measurement_bounds,
)


DEFAULT_DATASET_PATH = ROOT / "benchmarks" / "datasets" / "primata.txt"
DEFAULT_PDF_GRAPHS = ["Tensão"]
DAILY_PDF_MAX_WORKERS = 2
ENABLE_TRACEMALLOC = os.environ.get("MUG_BENCH_TRACEMALLOC", "auto").lower() != "0"


GRAPH_BUILDERS: dict[str, Callable[[ProcessedData], Any]] = {
    "Tensão": lambda processed: create_tension_graph(processed, show_logo=False),
    "Corrente": lambda processed: create_current_graph(processed, show_logo=False),
    "Potência Ativa": lambda processed: create_active_power_graph(processed, show_logo=False),
    "Potência Aparente": lambda processed: create_apparent_power_graph(processed, show_logo=False),
    "Fator de Potência": lambda processed: create_pf_graph(processed, show_logo=False),
    "DHT Tensão": lambda processed: create_dht_voltage_graph(processed, show_logo=False),
    "DHT Corrente": lambda processed: create_dht_current_graph(processed, show_logo=False),
    "Deseq. Tensão": lambda processed: create_tension_imbalance_graph(processed, show_logo=False),
    "Deseq. Corrente": lambda processed: create_current_imbalance_graph(processed, show_logo=False),
    "Consumo": lambda processed: create_consumption_graph(processed, show_logo=False),
    "Tensão x Corrente": lambda processed: create_combined_vxi_graph(processed, show_logo=False),
    "kW x kVA": lambda processed: create_combined_kwxkva_graph(processed, show_logo=False),
}


@dataclass
class TimedResult:
    seconds: float
    memory_peak_mb: float | None
    rss_peak_mb: float | None
    rss_delta_mb: float | None
    value: Any


def normalize_version(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError("version must not be empty")
    return clean if clean.lower().startswith("v") else f"v{clean}"


def rss_mb() -> float | None:
    if psutil is None:
        return None
    return psutil.Process().memory_info().rss / (1024 * 1024)


def timed(func: Callable[[], Any]) -> TimedResult:
    rss_start = rss_mb()
    rss_peak = rss_start
    stop_sampling = threading.Event()

    def sample_rss() -> None:
        nonlocal rss_peak
        while not stop_sampling.is_set():
            current = rss_mb()
            if current is not None:
                rss_peak = current if rss_peak is None else max(rss_peak, current)
            time.sleep(0.02)

    sampler = None
    if psutil is not None:
        sampler = threading.Thread(target=sample_rss, daemon=True)
        sampler.start()

    use_tracemalloc = ENABLE_TRACEMALLOC and psutil is None
    if use_tracemalloc:
        tracemalloc.start()

    start = time.perf_counter()
    try:
        value = func()
    finally:
        seconds = time.perf_counter() - start
        stop_sampling.set()
        if sampler is not None:
            sampler.join(timeout=1)

    memory_peak_mb = None
    if use_tracemalloc:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        memory_peak_mb = peak / (1024 * 1024)

    rss_end = rss_mb()
    if rss_end is not None:
        rss_peak = rss_end if rss_peak is None else max(rss_peak, rss_end)

    rss_delta = None if rss_start is None or rss_end is None else rss_end - rss_start
    return TimedResult(
        seconds=seconds,
        memory_peak_mb=memory_peak_mb,
        rss_peak_mb=rss_peak,
        rss_delta_mb=rss_delta,
        value=value,
    )


def input_data_for(dataset_path: Path) -> InputData:
    return InputData(
        company="ASD",
        city="Benchmark",
        equipment_type=EQUIPMENT_TYPE_TRAFO,
        equipment_reference="TR-01",
        equipment_value=500.0,
        local="Benchmark",
        revision="00",
        excel_path=dataset_path,
    )


def processed_with_dataframe(original: ProcessedData, dataframe: pd.DataFrame) -> ProcessedData:
    return ProcessedData(
        company=original.company,
        city=original.city,
        trafo=original.trafo,
        local=original.local,
        revision=original.revision,
        excel_path=original.excel_path,
        dataframe=dataframe,
        integration_time=original.integration_time,
        tension=original.tension,
        equipment_type=original.equipment_type,
        equipment_reference=original.equipment_reference,
        equipment_value=original.equipment_value,
    )


def measure_startup() -> dict[str, Any]:
    command = [
        sys.executable,
        "-c",
        "import time; t=time.perf_counter(); import app; print(time.perf_counter()-t)",
    ]
    start = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    total = time.perf_counter() - start
    import_seconds = float(completed.stdout.strip().splitlines()[-1])
    return {
        "total_subprocess_seconds": total,
        "app_import_seconds": import_seconds,
    }


def measure_graphs(processed: ProcessedData) -> tuple[dict[str, Any], float]:
    graph_results: dict[str, Any] = {}
    total = 0.0
    for graph_name in GRAPH_EXPORT_ORDER:
        result = timed(lambda name=graph_name: GRAPH_BUILDERS[name](processed))
        total += result.seconds
        graph_results[graph_name] = {
            "seconds": result.seconds,
            "memory_peak_mb": result.memory_peak_mb,
            "rss_peak_mb": result.rss_peak_mb,
            "rss_delta_mb": result.rss_delta_mb,
        }
    return graph_results, total


def export_and_record(
    processed: ProcessedData,
    output_dir: Path,
    selected_graphs: list[str],
    *,
    artifacts_retained: bool,
    target_name: str | None = None,
) -> dict[str, Any]:
    output_path = Path(
        export_figures_to_pdf(
            processed,
            selected_graphs,
            output_dir,
            zoom_mode=False,
        )
    )
    if target_name is not None:
        target_path = ensure_unique_pdf_path(output_dir / target_name)
        output_path.replace(target_path)
        output_path = target_path
    return {
        "path": str(output_path) if artifacts_retained else None,
        "filename": output_path.name,
        "retained": artifacts_retained,
        "size_bytes": output_path.stat().st_size,
        "graphs": selected_graphs,
    }


def sec(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def build_report(results: dict[str, Any]) -> str:
    dataset = results["dataset"]
    metrics = results["metrics"]
    pdfs = results["pdf_outputs"]

    lines = [
        f"# MUG {results['run_id']} Benchmark",
        "",
        "## Environment",
        "",
        f"- Created at: `{results['created_at']}`",
        f"- Version: `{results['run_id']}`",
        f"- Git commit: `{results['environment']['git_commit'] or 'n/a'}`",
        f"- Python: `{results['environment']['python']}`",
        f"- Platform: `{results['environment']['platform']}`",
        f"- Machine: `{results['environment']['machine']}`",
        f"- psutil available: `{results['environment']['psutil_available']}`",
        f"- tracemalloc enabled: `{results['environment']['tracemalloc_enabled']}`",
        f"- PDF artifacts retained: `{results['artifacts']['retained']}`",
        "",
        "## Dataset",
        "",
        f"- Path: `{dataset['path']}`",
        f"- Rows: `{dataset['rows']}`",
        f"- Columns: `{dataset['columns']}`",
        f"- Integration time: `{dataset['integration_time_seconds']} s`",
        f"- Measurement start: `{dataset['start']}`",
        f"- Measurement end: `{dataset['end']}`",
        f"- Detected days: `{dataset['detected_days']}`",
        f"- Complete days: `{dataset['complete_days']}`",
        f"- Incomplete days: `{dataset['incomplete_days']}`",
        "",
        "## Test Steps",
        "",
        "1. Measured startup by importing `app` in a subprocess.",
        "2. Loaded and parsed the real dataset through `process_input_data`.",
        "3. Generated all graph figures once through the same graph builders used by the UI.",
        "4. Applied a multi-day time filter through `core.time_filter.apply_time_filter`.",
        "5. Exported one current-measurement PDF.",
        "6. Exported one custom single PDF using a selected interval.",
        "7. Exported one custom daily PDF per detected day.",
        "",
        "## Timing Results",
        "",
        "| Metric | Seconds | Tracemalloc Peak MB | RSS Peak MB | RSS Delta MB |",
        "|---|---:|---:|---:|---:|",
        f"| Startup subprocess | {sec(metrics['startup']['total_subprocess_seconds'])} | n/a | n/a | n/a |",
        f"| App import | {sec(metrics['startup']['app_import_seconds'])} | n/a | n/a | n/a |",
        f"| File loading/parsing ETL | {sec(metrics['etl']['seconds'])} | {sec(metrics['etl']['memory_peak_mb'])} | {sec(metrics['etl']['rss_peak_mb'])} | {sec(metrics['etl']['rss_delta_mb'])} |",
        f"| Initial graph generation | {sec(metrics['graph_generation']['total_seconds'])} | n/a | n/a | n/a |",
        f"| Time selection/filter application | {sec(metrics['time_filter']['seconds'])} | {sec(metrics['time_filter']['memory_peak_mb'])} | {sec(metrics['time_filter']['rss_peak_mb'])} | {sec(metrics['time_filter']['rss_delta_mb'])} |",
        f"| Current measurement PDF export | {sec(metrics['current_pdf_export']['seconds'])} | {sec(metrics['current_pdf_export']['memory_peak_mb'])} | {sec(metrics['current_pdf_export']['rss_peak_mb'])} | {sec(metrics['current_pdf_export']['rss_delta_mb'])} |",
        f"| Custom single PDF export | {sec(metrics['custom_single_pdf_export']['seconds'])} | {sec(metrics['custom_single_pdf_export']['memory_peak_mb'])} | {sec(metrics['custom_single_pdf_export']['rss_peak_mb'])} | {sec(metrics['custom_single_pdf_export']['rss_delta_mb'])} |",
        f"| Custom daily PDF export | {sec(metrics['custom_daily_pdf_export']['seconds'])} | {sec(metrics['custom_daily_pdf_export']['memory_peak_mb'])} | {sec(metrics['custom_daily_pdf_export']['rss_peak_mb'])} | {sec(metrics['custom_daily_pdf_export']['rss_delta_mb'])} |",
        "",
        "## Graph Generation",
        "",
        "| Graph | Seconds | Tracemalloc Peak MB | RSS Peak MB | RSS Delta MB |",
        "|---|---:|---:|---:|---:|",
    ]

    for graph_name, graph_metric in metrics["graph_generation"]["graphs"].items():
        lines.append(
            f"| {graph_name} | {sec(graph_metric['seconds'])} | "
            f"{sec(graph_metric['memory_peak_mb'])} | "
            f"{sec(graph_metric['rss_peak_mb'])} | "
            f"{sec(graph_metric['rss_delta_mb'])} |"
        )

    lines.extend(
        [
            "",
            "## PDF Outputs",
            "",
            f"- Selected graphs for PDF timing: `{', '.join(results['pdf_selected_graphs'])}`",
            f"- Current measurement PDFs generated: `{len(pdfs['current'])}`",
            f"- Custom single PDFs generated: `{len(pdfs['custom_single'])}`",
            f"- Custom daily PDFs generated: `{len(pdfs['custom_daily'])}`",
            "",
            "| Type | Count | Total Size MB |",
            "|---|---:|---:|",
            f"| Current measurement | {len(pdfs['current'])} | {sum(item['size_bytes'] for item in pdfs['current']) / (1024 * 1024):.3f} |",
            f"| Custom single | {len(pdfs['custom_single'])} | {sum(item['size_bytes'] for item in pdfs['custom_single']) / (1024 * 1024):.3f} |",
            f"| Custom daily | {len(pdfs['custom_daily'])} | {sum(item['size_bytes'] for item in pdfs['custom_daily']) / (1024 * 1024):.3f} |",
            "",
            "## Output Files",
            "",
        ]
    )

    for group_name, group in pdfs.items():
        lines.append(f"### {group_name}")
        for item in group:
            output_label = item["path"] or item["filename"]
            retained_note = "" if item["retained"] else " (not retained)"
            lines.append(
                f"- `{output_label}` - {item['size_bytes'] / (1024 * 1024):.3f} MB"
                f"{retained_note}"
            )
        lines.append("")

    lines.extend(
        [
            "## Observations",
            "",
            "- ETL and graph generation are measured over the selected real benchmark dataset.",
            "- Memory uses RSS metrics when `psutil` is available.",
            "- When `psutil` is unavailable, Python allocation peak is measured with `tracemalloc` unless disabled with `MUG_BENCH_TRACEMALLOC=0`.",
            "- PDF timing uses the selected graph list to keep daily export runtime practical and reproducible.",
            "- By default, generated PDF artifacts are temporary and not retained in `docs/benchmarks/artifacts`.",
            "",
            "## Recommendations",
            "",
            "- Keep release benchmarks versioned and update `latest.md`/`latest.json` through this script.",
            "- Run with `--keep-artifacts` only when PDF artifacts must be inspected or published.",
            "- Compare PDF timings by selected graph count because runtime scales with graph count and detected days.",
            "",
        ]
    )

    return "\n".join(lines)


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def resolve_artifact_dir(run_id: str, keep_artifacts: bool, artifact_dir: str | None) -> tuple[Path, bool]:
    if artifact_dir:
        return Path(artifact_dir).resolve(), True

    if keep_artifacts:
        return ROOT / "docs" / "benchmarks" / "artifacts" / run_id, True

    return Path(tempfile.mkdtemp(prefix=f"mug_benchmark_{run_id}_")), False


def write_outputs(run_id: str, results: dict[str, Any], report: str) -> None:
    benchmarks_dir = ROOT / "docs" / "benchmarks"
    runs_dir = benchmarks_dir / "runs"
    benchmarks_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    report_path = benchmarks_dir / f"{run_id}_benchmark.md"
    json_path = runs_dir / f"{run_id}.json"
    latest_md = benchmarks_dir / "latest.md"
    latest_json = benchmarks_dir / "latest.json"

    json_text = json.dumps(results, indent=2, ensure_ascii=False)
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(json_text, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")

    print(f"Wrote {report_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {latest_md}")
    print(f"Wrote {latest_json}")


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    run_id = normalize_version(args.version)
    dataset_path = Path(args.dataset)
    if not dataset_path.is_absolute():
        dataset_path = ROOT / dataset_path
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    artifact_dir, artifacts_retained = resolve_artifact_dir(
        run_id,
        args.keep_artifacts,
        args.artifact_dir,
    )
    if artifact_dir.exists() and artifacts_retained:
        shutil.rmtree(artifact_dir)
    (artifact_dir / "current").mkdir(parents=True, exist_ok=True)
    (artifact_dir / "custom_single").mkdir(parents=True, exist_ok=True)
    (artifact_dir / "custom_daily").mkdir(parents=True, exist_ok=True)

    selected_graphs = list(args.pdf_graphs or DEFAULT_PDF_GRAPHS)

    try:
        startup = measure_startup()
        etl_result = timed(lambda: process_input_data(input_data_for(dataset_path)))
        processed: ProcessedData = etl_result.value
        start, end = get_measurement_bounds(processed.dataframe)
        days = detect_measurement_days(processed.dataframe, processed.integration_time)

        graph_metrics, graph_total = measure_graphs(processed)

        selected_days = days[: min(3, len(days))]
        if len(selected_days) >= 2:
            filter_start = selected_days[0].start_datetime
            filter_end = selected_days[-1].end_datetime
        else:
            filter_start = start
            filter_end = end

        filter_result = timed(
            lambda: apply_time_filter(
                processed.dataframe,
                custom_time_filter(filter_start, filter_end, "Benchmark custom interval"),
            )
        )
        filtered_dataframe: pd.DataFrame = filter_result.value
        filtered_processed = processed_with_dataframe(processed, filtered_dataframe)

        current_pdf = timed(
            lambda: export_and_record(
                processed,
                artifact_dir / "current",
                selected_graphs,
                artifacts_retained=artifacts_retained,
            )
        )
        custom_single_pdf = timed(
            lambda: export_and_record(
                filtered_processed,
                artifact_dir / "custom_single",
                selected_graphs,
                artifacts_retained=artifacts_retained,
                target_name=build_custom_pdf_filename(processed.company, processed.revision),
            )
        )

        def export_daily_outputs() -> list[dict[str, Any]]:
            def export_day(day) -> dict[str, Any]:
                day_dataframe = apply_time_filter(
                    processed.dataframe,
                    custom_time_filter(day.start_datetime, day.end_datetime, day.label),
                )
                day_processed = processed_with_dataframe(processed, day_dataframe)
                return export_and_record(
                    day_processed,
                    artifact_dir / "custom_daily",
                    selected_graphs,
                    artifacts_retained=artifacts_retained,
                    target_name=build_daily_pdf_filename(processed.company, processed.revision, day.date),
                )

            with ThreadPoolExecutor(max_workers=DAILY_PDF_MAX_WORKERS) as executor:
                return list(executor.map(export_day, days))

        custom_daily_pdf = timed(export_daily_outputs)
        daily_outputs = custom_daily_pdf.value

        return {
            "schema_version": 2,
            "run_id": run_id,
            "version": run_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "dataset": {
                "path": str(dataset_path.relative_to(ROOT)),
                "rows": int(len(processed.dataframe)),
                "columns": int(len(processed.dataframe.columns)),
                "integration_time_seconds": processed.integration_time,
                "start": str(start),
                "end": str(end),
                "detected_days": len(days),
                "complete_days": sum(1 for day in days if day.status == "Complete"),
                "incomplete_days": sum(1 for day in days if day.status != "Complete"),
            },
            "environment": {
                "python": sys.version,
                "platform": sys.platform,
                "machine": platform.platform(),
                "executable": sys.executable,
                "git_commit": git_commit(),
                "psutil_available": psutil is not None,
                "tracemalloc_enabled": ENABLE_TRACEMALLOC and psutil is None,
            },
            "artifacts": {
                "directory": str(artifact_dir) if artifacts_retained else None,
                "retained": artifacts_retained,
            },
            "pdf_selected_graphs": selected_graphs,
            "metrics": {
                "startup": startup,
                "etl": {
                    "seconds": etl_result.seconds,
                    "memory_peak_mb": etl_result.memory_peak_mb,
                    "rss_peak_mb": etl_result.rss_peak_mb,
                    "rss_delta_mb": etl_result.rss_delta_mb,
                },
                "graph_generation": {
                    "total_seconds": graph_total,
                    "graphs": graph_metrics,
                },
                "time_filter": {
                    "seconds": filter_result.seconds,
                    "memory_peak_mb": filter_result.memory_peak_mb,
                    "rss_peak_mb": filter_result.rss_peak_mb,
                    "rss_delta_mb": filter_result.rss_delta_mb,
                    "rows": int(len(filtered_dataframe)),
                    "start": str(filter_start),
                    "end": str(filter_end),
                },
                "current_pdf_export": {
                    "seconds": current_pdf.seconds,
                    "memory_peak_mb": current_pdf.memory_peak_mb,
                    "rss_peak_mb": current_pdf.rss_peak_mb,
                    "rss_delta_mb": current_pdf.rss_delta_mb,
                },
                "custom_single_pdf_export": {
                    "seconds": custom_single_pdf.seconds,
                    "memory_peak_mb": custom_single_pdf.memory_peak_mb,
                    "rss_peak_mb": custom_single_pdf.rss_peak_mb,
                    "rss_delta_mb": custom_single_pdf.rss_delta_mb,
                },
                "custom_daily_pdf_export": {
                    "seconds": custom_daily_pdf.seconds,
                    "memory_peak_mb": custom_daily_pdf.memory_peak_mb,
                    "rss_peak_mb": custom_daily_pdf.rss_peak_mb,
                    "rss_delta_mb": custom_daily_pdf.rss_delta_mb,
                },
            },
            "pdf_outputs": {
                "current": [current_pdf.value],
                "custom_single": [custom_single_pdf.value],
                "custom_daily": daily_outputs,
            },
        }
    finally:
        if not artifacts_retained and artifact_dir.exists():
            shutil.rmtree(artifact_dir, ignore_errors=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MUG release benchmark.")
    parser.add_argument("--version", required=True, help="Release/version label, e.g. v1.4.0.")
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH.relative_to(ROOT)),
        help="Dataset path.",
    )
    parser.add_argument(
        "--pdf-graphs",
        nargs="+",
        default=DEFAULT_PDF_GRAPHS,
        help="Graph names to include in PDF export timings.",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Retain generated PDF artifacts under docs/benchmarks/artifacts/<version>.",
    )
    parser.add_argument(
        "--artifact-dir",
        default=None,
        help="Custom directory for generated PDF artifacts. Implies retention.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = normalize_version(args.version)
    results = run_benchmark(args)
    report = build_report(results)
    write_outputs(run_id, results, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
