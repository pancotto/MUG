# MUG - Copilot Instructions

These instructions guide AI agents working on the MUG project. Follow them to preserve the current architecture, packaging flow, and PDF export behavior.

## Project Purpose

MUG is a Windows desktop application for graphical analysis of electrical quantities. It uses:

- Python
- PySide6 for the desktop UI
- Pandas for data processing
- Plotly for graph generation
- QWebEngineView for interactive graph rendering
- Kaleido/Chromium for static graph rendering
- FPDF for PDF assembly
- PyInstaller/Inno Setup for Windows distribution

The application is used in an operational/reporting context. Stability, predictable output, and compatibility with packaged builds are more important than broad refactors or architectural novelty.

## Current Architecture

The application follows a linear desktop workflow:

```text
ui.input_page.InputPage
  -> core.models.InputData
  -> core.excel_reader.process_input_data()
  -> core.models.ProcessedData
  -> ui.main_window.MainWindow.set_processed_data()
  -> ui.graph_page.GraphPage.load_processed_data()
  -> core.graph_builder.create_*_graph()
  -> QWebEngineView interactive graphs
  -> ui.graph_page.PdfExportTab
  -> core.pdf_exporter.export_figures_to_pdf()
```

### UI Layer

- `app.py` starts the PySide6 application and opens `MainWindow`.
- `ui/main_window.py` owns navigation between the input page and graph page.
- `ui/input_page.py` collects user inputs, validates the form, selects the data file, and starts processing in a `QThread`.
- `ui/graph_page.py` renders Plotly graphs inside `QWebEngineView`, synchronizes zoom, and exposes the PDF export tab.

Do not move heavy processing back onto the UI thread. File processing and PDF export currently run through worker objects in `QThread` to keep the interface responsive.

### Data Contracts

The main data contracts are in `core/models.py`:

- `InputData`: raw user form values plus the selected data file path.
- `ProcessedData`: normalized, processed data used by graphs and PDF export.

Preserve the `ProcessedData` architecture. Graph generation and PDF export should continue to consume `ProcessedData` rather than reading files directly or depending on UI widgets.

Important `ProcessedData` responsibilities:

- stores user/report metadata;
- stores the normalized Pandas `DataFrame`;
- stores inferred integration time and nominal tension;
- provides compatibility properties such as `trafo`;
- handles transformer and circuit breaker reference calculations;
- exposes title/label helpers used by graph builders.

When adding data needed by graphs or PDF export, prefer extending `ProcessedData` carefully rather than passing loose dictionaries or UI state through the codebase.

### File Reading And ETL

File reading and ETL live in `core/excel_reader.py`.

Supported inputs:

- Primata `.xlsx`;
- Primata `.txt`;
- Embrasul `.txt`.

The ETL design intentionally converts all supported inputs into a common internal DataFrame shape compatible with the graph builders. Embrasul files are mapped to Primata-like column names so the rest of the system can remain source-agnostic.

Preserve this flow:

```text
detect/read source file
  -> normalize source-specific columns
  -> prepare_common_dataframe()
  -> infer_integration_time()
  -> infer_nominal_tension()
  -> return ProcessedData
```

Avoid adding source-specific branching inside graph builders unless absolutely necessary. Prefer normalizing data earlier in `core/excel_reader.py`.

### Graph Generation

Graph builders live in `core/graph_builder.py`.

The UI creates graphs through methods such as:

- `create_tension_graph`
- `create_current_graph`
- `create_active_power_graph`
- `create_apparent_power_graph`
- `create_pf_graph`
- `create_tension_imbalance_graph`
- `create_current_imbalance_graph`
- `create_dht_voltage_graph`
- `create_dht_current_graph`
- `create_consumption_graph`
- `create_combined_vxi_graph`
- `create_combined_kwxkva_graph`

Each builder should accept `ProcessedData` and return a `plotly.graph_objects.Figure`.

Preserve these conventions:

- use `ProcessedData.dataframe` as the graph source;
- keep graph title metadata consistent across graph types;
- keep company, city, local, equipment description, tension, integration time, and revision in graph titles where currently expected;
- preserve PRODIST/ANEEL limit annotations where already implemented;
- use `apply_common_layout()` for shared Plotly layout behavior;
- keep combined graphs composed from existing graph builders where practical.

The interactive UI renders Plotly figures as HTML through `fig.to_html()` and loads them into `QWebEngineView`. Zoom synchronization uses JavaScript plus `QWebChannel` through `PlotBridge`. Do not replace this flow without a specific requirement and regression testing.

### PDF Export

PDF export is split between:

- `ui/graph_page.py`: user selection, destination folder, zoom-state handling, worker thread;
- `core/pdf_exporter.py`: graph reconstruction, static image rendering, PDF assembly.

Preserve the current PDF flow:

```text
selected graph names
  -> optional zoom-filtered ProcessedData
  -> build_pdf_figures()
  -> create_*_graph(show_logo=True)
  -> apply_pdf_visual_standard()
  -> Plotly/Kaleido to_image()
  -> temporary JPEG files
  -> FPDF A4 landscape
  -> one graph per page
  -> cleanup temporary files
```

Important constraints:

- keep `GRAPH_EXPORT_ORDER` as the source of export ordering;
- keep A4 landscape output unless explicitly requested;
- keep one graph per page unless explicitly requested;
- preserve selected-graphs-only export;
- preserve zoom-mode export behavior;
- keep PDF generation off the UI thread;
- preserve cleanup of temporary image files;
- keep error messages helpful when Kaleido/Chromium rendering fails.

Kaleido v1 requires a working Chrome/Chromium. The project supports packaged Chromium discovery through `configure_kaleido_browser_path()`. Do not remove or bypass this behavior.

## PyInstaller Compatibility

The application is distributed as a Windows executable. Code must remain compatible with normal source execution and PyInstaller packaged execution.

When dealing with paths:

- use `pathlib.Path`;
- account for `sys.frozen` and `sys._MEIPASS` patterns where runtime assets are involved;
- prefer existing helpers in `core/paths.py` and existing runtime path patterns;
- avoid hard-coded absolute development paths;
- avoid assuming the current working directory is the project root;
- avoid requiring external files that are not packaged.

When adding dependencies:

- update `requirements.txt` only when truly necessary;
- consider whether the dependency works under PyInstaller;
- avoid dependencies that require complex system installation on client machines;
- preserve the embedded Chromium/Kaleido PDF path.

## Stability Rules

This project prioritizes stable report generation and packaged reliability.

Do:

- make small, targeted changes;
- preserve existing public function names unless there is a deliberate migration;
- keep backward-compatible column handling where possible;
- validate behavior with representative Primata and Embrasul inputs when available;
- keep UI responsiveness by using worker threads for expensive work;
- keep user-facing error messages clear and actionable.

Do not:

- perform aggressive refactors without explicit approval;
- replace the `ProcessedData` pipeline with ad hoc data passing;
- move file reading logic into UI or graph modules;
- make graph builders read files directly;
- change PDF page order, sizing, or static rendering flow casually;
- remove PyInstaller runtime path handling;
- introduce network requirements into core processing, graphing, or PDF export;
- make unrelated formatting or style churn.

## Current Project Priorities

Prioritize work in this order:

1. Preserve correctness of electrical graphs and report outputs.
2. Preserve compatibility with Primata `.xlsx`, Primata `.txt`, and Embrasul `.txt`.
3. Preserve PDF export reliability in packaged Windows builds.
4. Preserve UI responsiveness during processing and export.
5. Improve maintainability through small, local changes.
6. Add tests or verification scripts for ETL and graph/PDF behavior where practical.
7. Improve user-facing errors and diagnostics without changing core flows.

## Development Conventions

- Use Python idioms already present in the codebase.
- Prefer `Path` over string path manipulation.
- Keep source-specific parsing in `core/excel_reader.py`.
- Keep graph-specific behavior in `core/graph_builder.py`.
- Keep PDF-specific static rendering and assembly in `core/pdf_exporter.py`.
- Keep UI orchestration in `ui/*.py`.
- Use dataclasses for structured cross-layer data when appropriate.
- Prefer explicit errors over silent fallback when required input columns are missing.
- Keep comments concise and useful.
- Avoid broad renames unless requested.
- Avoid touching unrelated files.

## Verification Guidance

For ETL changes:

- verify supported file types still load;
- check `Datetime` parsing and sorting;
- check numeric parsing with comma and dot decimal formats;
- check inferred integration time;
- check inferred nominal tension;
- check transformer and breaker calculations.

For graph changes:

- verify all graph builders return Plotly `Figure` objects;
- verify expected columns are still accepted;
- verify titles, legends, limits, and annotations remain readable;
- verify zoom synchronization still rebuilds all graph tabs.

For PDF changes:

- verify selected graph export;
- verify default graph selection;
- verify zoomed export;
- verify file naming;
- verify one graph per A4 landscape page;
- verify temporary files are cleaned up;
- verify Kaleido/Chromium failure messages remain useful.

For packaging-related changes:

- verify source execution with `python app.py`;
- verify packaged execution path assumptions;
- verify assets and embedded browser discovery;
- avoid adding assumptions that only work in the development workspace.
