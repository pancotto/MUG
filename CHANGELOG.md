# Changelog

## v1.3.1 - 2026-05-11

Release focused on measurement, release hardening, startup cost reduction, and low-risk ETL optimizations while preserving the current UI, graph behavior, PDF export flow, PyInstaller compatibility, and the `ProcessedData` architecture.

### Added

- Profiling infrastructure for ETL, graph generation, graph rebuild/zoom, PDF export, per-graph export timing, and approximate memory reporting.
- Reproducible benchmark scripts with JSON, Markdown, logs, and historical comparison support.
- Architecture documentation for ETL, `ProcessedData`, Plotly rendering, PDF export, and core/UI responsibilities.
- Copilot/agent project instructions focused on stability, PyInstaller compatibility, PDF export preservation, and conservative development conventions.
- Official release notes directory at `docs/releases/`.
- Official release benchmark reference directory at `docs/benchmarks/releases/`.

### Changed

- Lazy-loaded PDF export implementation so `core.pdf_exporter`, Kaleido-related code, and PDF-only dependencies are loaded only when exporting.
- Lazy-loaded update checker so update-checking dependencies are loaded only when the update workflow runs.
- Optimized Primata TXT datetime parsing with a vectorized fast path for the known `dd/mm/yy` + `HH:MM:SS` format, preserving the existing fallback.
- Preserved/reused numeric dtypes in the ETL pipeline to avoid redundant numeric conversion, especially for Primata XLSX.
- Updated project version from `1.3.0` to `1.3.1`.

### Compatibility

- Preserves the current graph behavior and visual layout.
- Preserves the existing PDF export workflow.
- Preserves support for Primata XLSX, Primata TXT, and Embrasul TXT.
- Preserves PyInstaller onedir packaging and Inno Setup installer flow.
- Keeps benchmark datasets and generated benchmark artifacts out of Git by default.

## v1.3.0

- Previous stable release baseline.
