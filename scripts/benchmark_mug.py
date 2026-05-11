from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.profiling import get_memory_mb, get_profile_logger


DATASET_CANDIDATES = [
    PROJECT_ROOT / "benchmarks" / "datasets" / "primata.xlsx",
    PROJECT_ROOT / "benchmarks" / "datasets" / "primata.txt",
    PROJECT_ROOT / "benchmarks" / "datasets" / "embrasul.txt",
]

RESULTS_DIR = PROJECT_ROOT / "docs" / "benchmarks"
RUNS_DIR = RESULTS_DIR / "runs"
LOGS_DIR = RESULTS_DIR / "logs"
ARTIFACTS_DIR = RESULTS_DIR / "artifacts"


def configure_logging(run_id: str) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"{run_id}.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    root_logger = logging.getLogger("mug.benchmark")
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    profile_logger = get_profile_logger()
    profile_file_handler = logging.FileHandler(log_path, encoding="utf-8")
    profile_file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [PROFILE] %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    profile_logger.addHandler(profile_file_handler)

    return log_path


def logger() -> logging.Logger:
    return logging.getLogger("mug.benchmark")


def now_run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def memory_snapshot() -> float | None:
    return get_memory_mb()


@contextmanager
def measured_step(result: dict[str, Any], name: str, **details):
    start = time.perf_counter()
    mem_start = memory_snapshot()
    logger().info("start %s %s", name, format_details(details))
    status = "ok"

    try:
        yield
    except Exception:
        status = "failed"
        raise
    finally:
        end = time.perf_counter()
        mem_end = memory_snapshot()
        elapsed = end - start
        mem_delta = None if mem_start is None or mem_end is None else mem_end - mem_start
        result[name] = {
            "seconds": elapsed,
            "memory_start_mb": mem_start,
            "memory_end_mb": mem_end,
            "memory_delta_mb": mem_delta,
            "status": status,
            "details": details,
        }
        logger().info(
            "end %s status=%s seconds=%.3f mem_start=%s mem_end=%s mem_delta=%s",
            name,
            status,
            elapsed,
            format_memory(mem_start),
            format_memory(mem_end),
            format_memory(mem_delta),
        )


def measure_call(name: str, fn: Callable[[], Any], **details) -> tuple[Any, dict[str, Any]]:
    measurement: dict[str, Any] = {}
    with measured_step(measurement, name, **details):
        value = fn()
    return value, measurement[name]


def format_memory(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f} MB"


def format_details(details: dict[str, Any]) -> str:
    if not details:
        return ""
    return " ".join(f"{key}={value}" for key, value in details.items() if value is not None)


def choose_dataset(dataset_arg: str | None) -> Path:
    if dataset_arg:
        dataset = Path(dataset_arg)
        if not dataset.is_absolute():
            dataset = PROJECT_ROOT / dataset
        if not dataset.exists():
            raise FileNotFoundError(f"Dataset not found: {dataset}")
        return dataset

    for candidate in DATASET_CANDIDATES:
        if candidate.exists():
            return candidate

    expected = "\n".join(f"- {path.relative_to(PROJECT_ROOT)}" for path in DATASET_CANDIDATES)
    raise FileNotFoundError(
        "No benchmark dataset found. Add one of these files:\n"
        f"{expected}\n"
        "Or pass --dataset path\\to\\file.xlsx."
    )


def make_input_data(dataset: Path, args: argparse.Namespace) -> InputData:
    from core.models import InputData

    return InputData(
        company=args.company,
        city=args.city,
        equipment_type=args.equipment_type,
        equipment_reference=args.equipment_reference,
        equipment_value=args.equipment_value,
        local=args.local,
        revision=args.revision,
        excel_path=dataset,
    )


def make_processed_for_zoom(processed):
    from core.models import ProcessedData

    df = processed.dataframe.copy()
    if len(df) >= 4:
        start_index = len(df) // 4
        end_index = max(start_index + 1, (len(df) * 3) // 4)
        df = df.iloc[start_index:end_index].copy()

    return ProcessedData(
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


def get_graph_builders(show_logo: bool = False) -> dict[str, Callable[[Any], Any]]:
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

    return {
        "Tensao": lambda processed: create_tension_graph(processed, show_logo=show_logo),
        "Corrente": lambda processed: create_current_graph(processed, show_logo=show_logo),
        "Potencia Ativa": lambda processed: create_active_power_graph(processed, show_logo=show_logo),
        "Potencia Aparente": lambda processed: create_apparent_power_graph(processed, show_logo=show_logo),
        "Fator de Potencia": lambda processed: create_pf_graph(processed, show_logo=show_logo),
        "Deseq. Tensao": lambda processed: create_tension_imbalance_graph(processed, show_logo=show_logo),
        "Deseq. Corrente": lambda processed: create_current_imbalance_graph(processed, show_logo=show_logo),
        "Consumo": lambda processed: create_consumption_graph(processed, show_logo=show_logo),
        "DHT Tensao": lambda processed: create_dht_voltage_graph(processed, show_logo=show_logo),
        "DHT Corrente": lambda processed: create_dht_current_graph(processed, show_logo=show_logo),
        "Tensao x Corrente": lambda processed: create_combined_vxi_graph(processed, show_logo=show_logo),
        "kW x kVA": lambda processed: create_combined_kwxkva_graph(processed, show_logo=show_logo),
    }


def get_pdf_graph_builders() -> dict[str, Callable[[Any], Any]]:
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

    return {
        "Tensão": lambda processed: create_tension_graph(processed, show_logo=True),
        "Corrente": lambda processed: create_current_graph(processed, show_logo=True),
        "Potência Ativa": lambda processed: create_active_power_graph(processed, show_logo=True),
        "Potência Aparente": lambda processed: create_apparent_power_graph(processed, show_logo=True),
        "Fator de Potência": lambda processed: create_pf_graph(processed, show_logo=True),
        "Deseq. Tensão": lambda processed: create_tension_imbalance_graph(processed, show_logo=True),
        "Deseq. Corrente": lambda processed: create_current_imbalance_graph(processed, show_logo=True),
        "Consumo": lambda processed: create_consumption_graph(processed, show_logo=True),
        "DHT Tensão": lambda processed: create_dht_voltage_graph(processed, show_logo=True),
        "DHT Corrente": lambda processed: create_dht_current_graph(processed, show_logo=True),
        "Tensão x Corrente": lambda processed: create_combined_vxi_graph(processed, show_logo=True),
        "kW x kVA": lambda processed: create_combined_kwxkva_graph(processed, show_logo=True),
    }


def benchmark_startup() -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    code = (
        "import time\n"
        "start = time.perf_counter()\n"
        "import app\n"
        "print(f'{time.perf_counter() - start:.6f}')\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    output = completed.stdout.strip().splitlines()
    import_seconds = float(output[-1]) if output else 0.0
    return {"app_import_seconds": import_seconds}


def benchmark_graph_generation(processed) -> dict[str, Any]:
    graph_results: dict[str, Any] = {}
    figures: dict[str, Any] = {}

    for graph_name, builder in get_graph_builders(show_logo=False).items():
        fig, measurement = measure_call(
            f"graph:{graph_name}",
            lambda builder=builder: builder(processed),
            rows=len(processed.dataframe),
        )
        figures[graph_name] = fig
        graph_results[graph_name] = measurement

    return {
        "graphs": graph_results,
        "graph_count": len(figures),
    }


def benchmark_pdf_export(processed, output_dir: Path, selected_graphs: list[str]) -> dict[str, Any]:
    from fpdf import FPDF
    from core.pdf_exporter import (
        GRAPH_EXPORT_ORDER,
        A4_LANDSCAPE_WIDTH_MM,
        A4_LANDSCAPE_HEIGHT_MM,
        LEFT_MARGIN_MM,
        TOP_MARGIN_MM,
        RIGHT_MARGIN_MM,
        BOTTOM_MARGIN_MM,
        apply_pdf_visual_standard,
        save_figure_as_jpeg,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="mug_benchmark_pdf_"))
    temp_images: list[Path] = []
    graph_results: dict[str, Any] = {}

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    usable_width = A4_LANDSCAPE_WIDTH_MM - (LEFT_MARGIN_MM + RIGHT_MARGIN_MM)
    usable_height = A4_LANDSCAPE_HEIGHT_MM - (TOP_MARGIN_MM + BOTTOM_MARGIN_MM)
    pdf_path = output_dir / "benchmark-export.pdf"

    try:
        pdf_builders = get_pdf_graph_builders()

        for graph_name in GRAPH_EXPORT_ORDER:
            if graph_name not in selected_graphs:
                continue

            builder = pdf_builders.get(graph_name)
            if builder is None:
                continue

            graph_measurements: dict[str, Any] = {}

            fig, build_measurement = measure_call(
                f"pdf_build:{graph_name}",
                lambda builder=builder: apply_pdf_visual_standard(
                    graph_name,
                    builder(processed),
                    processed,
                    zoom_mode=False,
                ),
                rows=len(processed.dataframe),
            )
            graph_measurements["build"] = build_measurement

            temp_image_path = temp_dir / f"{safe_filename(graph_name)}.jpg"
            _, image_measurement = measure_call(
                f"pdf_image:{graph_name}",
                lambda fig=fig, path=temp_image_path, name=graph_name: save_figure_as_jpeg(
                    fig,
                    path,
                    graph_name=name,
                ),
            )
            graph_measurements["image"] = image_measurement
            temp_images.append(temp_image_path)

            _, page_measurement = measure_call(
                f"pdf_page:{graph_name}",
                lambda path=temp_image_path: add_pdf_page(pdf, path, usable_width, usable_height),
            )
            graph_measurements["page"] = page_measurement
            graph_results[graph_name] = graph_measurements

        _, write_measurement = measure_call(
            "pdf_write",
            lambda: pdf.output(str(pdf_path)),
            pages=len(graph_results),
        )

        return {
            "path": str(pdf_path),
            "graphs": graph_results,
            "write": write_measurement,
            "graph_count": len(graph_results),
        }
    finally:
        for image_path in temp_images:
            if image_path.exists():
                image_path.unlink(missing_ok=True)
        if temp_dir.exists():
            try:
                temp_dir.rmdir()
            except OSError:
                pass


def add_pdf_page(pdf, image_path: Path, usable_width: float, usable_height: float) -> None:
    from core.pdf_exporter import LEFT_MARGIN_MM, TOP_MARGIN_MM

    pdf.add_page()
    pdf.image(
        str(image_path),
        x=LEFT_MARGIN_MM,
        y=TOP_MARGIN_MM,
        w=usable_width,
        h=usable_height,
    )


def safe_filename(value: str) -> str:
    replacements = {
        " ": "_",
        "/": "_",
        "\\": "_",
        "ç": "c",
        "ã": "a",
        "ê": "e",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ã": "a",
        "õ": "o",
        "â": "a",
        "ô": "o",
    }
    result = value
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


def build_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# MUG Benchmark {result['run_id']}",
        "",
        "## Environment",
        "",
        f"- Dataset: `{result['dataset']['path']}`",
        f"- Rows: `{result['dataset'].get('rows', 'n/a')}`",
        f"- Columns: `{result['dataset'].get('columns', 'n/a')}`",
        f"- Python: `{result['environment']['python']}`",
        f"- Platform: `{result['environment']['platform']}`",
        "",
        "## Summary",
        "",
        "| Metric | Seconds | Memory Delta |",
        "|---|---:|---:|",
    ]

    for key in ["startup", "etl", "initial_graph_generation", "zoom_rebuild", "pdf_export"]:
        metric = result["metrics"].get(key)
        if metric:
            lines.append(
                f"| {key} | {metric['seconds']:.3f} | {format_memory(metric.get('memory_delta_mb'))} |"
            )

    lines.extend(["", "## Graph Generation", "", "| Graph | Seconds | Memory Delta |", "|---|---:|---:|"])
    graph_metrics = result["metrics"].get("initial_graphs", {}).get("graphs", {})
    for graph_name, metric in graph_metrics.items():
        lines.append(
            f"| {graph_name} | {metric['seconds']:.3f} | {format_memory(metric.get('memory_delta_mb'))} |"
        )

    lines.extend(["", "## Zoom Rebuild", "", "| Graph | Seconds | Memory Delta |", "|---|---:|---:|"])
    zoom_metrics = result["metrics"].get("zoom_graphs", {}).get("graphs", {})
    for graph_name, metric in zoom_metrics.items():
        lines.append(
            f"| {graph_name} | {metric['seconds']:.3f} | {format_memory(metric.get('memory_delta_mb'))} |"
        )

    lines.extend(["", "## PDF Export", "", "| Graph | Build | Image | Page |", "|---|---:|---:|---:|"])
    pdf_graphs = result["metrics"].get("pdf_graphs", {}).get("graphs", {})
    for graph_name, metrics in pdf_graphs.items():
        lines.append(
            "| {name} | {build:.3f} | {image:.3f} | {page:.3f} |".format(
                name=graph_name,
                build=metrics["build"]["seconds"],
                image=metrics["image"]["seconds"],
                page=metrics["page"]["seconds"],
            )
        )

    lines.extend([
        "",
        "## Artifacts",
        "",
        f"- JSON: `{result['artifacts']['json']}`",
        f"- Markdown: `{result['artifacts']['markdown']}`",
        f"- Log: `{result['artifacts']['log']}`",
        f"- PDF: `{result['artifacts'].get('pdf', 'n/a')}`",
        "",
    ])

    return "\n".join(lines)


def write_results(result: dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    run_json = RUNS_DIR / f"{result['run_id']}.json"
    run_md = RUNS_DIR / f"{result['run_id']}.md"
    latest_json = RESULTS_DIR / "latest.json"
    latest_md = RESULTS_DIR / "latest.md"

    result["artifacts"]["json"] = str(run_json.relative_to(PROJECT_ROOT))
    result["artifacts"]["markdown"] = str(run_md.relative_to(PROJECT_ROOT))

    markdown = build_markdown(result)
    json_text = json.dumps(result, indent=2, ensure_ascii=False)

    run_json.write_text(json_text + "\n", encoding="utf-8")
    latest_json.write_text(json_text + "\n", encoding="utf-8")
    run_md.write_text(markdown + "\n", encoding="utf-8")
    latest_md.write_text(markdown + "\n", encoding="utf-8")


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or now_run_id()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = configure_logging(run_id)

    dataset = choose_dataset(args.dataset)
    artifact_dir = ARTIFACTS_DIR / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": {
            "path": str(dataset.relative_to(PROJECT_ROOT) if dataset.is_relative_to(PROJECT_ROOT) else dataset),
            "suffix": dataset.suffix.lower(),
        },
        "environment": {
            "python": sys.version.replace("\n", " "),
            "platform": sys.platform,
            "executable": sys.executable,
        },
        "metrics": {},
        "artifacts": {
            "log": str(log_path.relative_to(PROJECT_ROOT)),
        },
    }

    logger().info("MUG benchmark run_id=%s dataset=%s", run_id, dataset)

    startup_result, startup_metric = measure_call("startup", benchmark_startup)
    startup_metric["details"].update(startup_result)
    result["metrics"]["startup"] = startup_metric

    from core.excel_reader import process_input_data

    input_data = make_input_data(dataset, args)
    processed, etl_metric = measure_call("etl", lambda: process_input_data(input_data), dataset=dataset.name)
    result["metrics"]["etl"] = etl_metric
    result["dataset"]["rows"] = len(processed.dataframe)
    result["dataset"]["columns"] = len(processed.dataframe.columns)

    initial_graphs, initial_graph_metric = measure_call(
        "initial_graph_generation",
        lambda: benchmark_graph_generation(processed),
        rows=len(processed.dataframe),
    )
    result["metrics"]["initial_graph_generation"] = initial_graph_metric
    result["metrics"]["initial_graphs"] = initial_graphs

    zoom_processed = make_processed_for_zoom(processed)
    zoom_graphs, zoom_metric = measure_call(
        "zoom_rebuild",
        lambda: benchmark_graph_generation(zoom_processed),
        rows=len(zoom_processed.dataframe),
    )
    result["metrics"]["zoom_rebuild"] = zoom_metric
    result["metrics"]["zoom_graphs"] = zoom_graphs

    if not args.skip_pdf:
        from core.pdf_exporter import GRAPH_EXPORT_ORDER

        selected_graphs = GRAPH_EXPORT_ORDER if args.pdf_graphs == "all" else args.pdf_graphs.split(",")
        pdf_output_dir = artifact_dir / "pdf"
        pdf_result, pdf_metric = measure_call(
            "pdf_export",
            lambda: benchmark_pdf_export(processed, pdf_output_dir, selected_graphs),
            selected=len(selected_graphs),
        )
        result["metrics"]["pdf_export"] = pdf_metric
        result["metrics"]["pdf_graphs"] = pdf_result
        result["artifacts"]["pdf"] = pdf_result["path"]

    write_results(result)
    logger().info("benchmark complete latest=%s", RESULTS_DIR / "latest.json")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run reproducible MUG performance benchmarks.")
    parser.add_argument("--dataset", help="Path to .xlsx or .txt benchmark dataset.")
    parser.add_argument("--run-id", help="Optional stable run id for reproducible output names.")
    parser.add_argument("--skip-pdf", action="store_true", help="Skip real PDF export.")
    parser.add_argument(
        "--pdf-graphs",
        default="all",
        help="Comma-separated PDF graph names, or 'all'. Names must match GRAPH_EXPORT_ORDER.",
    )
    parser.add_argument("--company", default="BENCHMARK")
    parser.add_argument("--city", default="VITORIA/ES")
    parser.add_argument("--equipment-type", default="TRAFO", choices=["TRAFO", "DISJUNTOR"])
    parser.add_argument("--equipment-reference", default="BENCHMARK")
    parser.add_argument("--equipment-value", type=float, default=500.0)
    parser.add_argument("--local", default="BENCHMARK")
    parser.add_argument("--revision", default="00")
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        run_benchmark(args)
        return 0
    except Exception as exc:
        logging.basicConfig(level=logging.ERROR, format="%(message)s")
        logging.error("Benchmark failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
