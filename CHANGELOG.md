# Changelog

## v1.4.3

### Startup UX

- Refined the splash screen into a more product-like startup surface with official ECOCEL PNG branding, restrained dark graphite styling and technical waveform motion.
- Added cycling startup messages, a thin activity sweep and a short finishing animation before the splash fades out.

### Compatibility

- No user-facing workflow changes.
- Preserved ETL logic, graph calculations, PDF export behavior, filename standards, report logic, selection logic and update-check semantics.

## v1.4.2

### Startup UX

- Added a lightweight PySide-only cinematic splash screen that appears before the main window is constructed.
- Added a dark, minimalist animated startup surface with centered MUG identity, sine-wave motion and fade transitions.
- Lazy-loaded the main window after the splash is visible to improve perceived startup responsiveness.

### Infrastructure

- Added a simple single-instance startup guard to reduce accidental multiple launches while MUG is already opening or running.
- Kept splash rendering independent from internet access, Chromium, Plotly, Kaleido, ETL, PDF export and graph generation.

### Tests

- Added splash import/startup tests to verify the splash module is lightweight and the app import path does not pull in main-window/update-check dependencies.

### Compatibility

- No user-facing workflow changes.
- Preserved ETL logic, graph calculations, PDF export behavior, filename standards, report logic, selection logic and update-check semantics.

## v1.4.1

### Infrastructure

- Moved startup update checking into a background worker so the main window can open normally when GitHub is slow, offline, blocked or returning errors.
- Added a safe release publication orchestrator with validation, tests, benchmark execution, build hooks, installer hooks, checksum reporting, git inspection and opt-in commit/tag/push/GitHub release steps.
- Added reusable GitHub Release notes generation from CHANGELOG data with optional installer SHA256 inclusion.
- Ignored generated benchmark artifact folders to reduce accidental commits of temporary PDFs.

### Tests

- Added update-check timeout/error tests without live internet.
- Added background update worker success/error tests.
- Added release-notes generation tests for the publication script.

### Compatibility

- No user-facing workflow changes.
- Preserved ETL logic, graph calculations, PDF export behavior, filename standards, report logic and filtering behavior.

## v1.4.0

### Quality and Infrastructure

- Added release validation for VERSION, README, CHANGELOG, installer metadata, UI fallback versions, duplicate version display tokens and benchmark pointers.
- Improved Windows build reproducibility by making the PyInstaller spec eligible for version control and hardening build_exe.bat error handling.
- Added ETL regression coverage for Primata TXT, Primata XLSX when available and Embrasul TXT fixtures.
- Added smoke coverage for all graph builders using a small processed dataset, including source-data mutation checks.
- Replaced the version-specific benchmark entry point with a generic release benchmark workflow while keeping the old script as a compatibility wrapper.
- Added benchmark outputs for versioned Markdown, versioned JSON and latest benchmark pointers.

### Compatibility

- No user-facing workflow changes.
- Preserved ETL logic, graph calculations, PDF export behavior, filename standards and filtering behavior.

## v1.3.9

### New Features

- Added optional "PERSONALIZAR TÍTULO" area in the EXPORTAR PDF tab.
- Added export-only metadata customization for Empresa, Cidade/ES, Revisão, Local, Referência/Tag and Potência/Corrente.
- Added filename metadata block after company name for all PDF export modes.

### Improvements

- Standardized PDF filenames as "GR - EMPRESA - LOCAL REFERÊNCIA VALOR - DATA - REV.pdf".
- Daily custom exports now use the same metadata standard with one file per measurement day.
- Customized export metadata is applied only to PDF titles and filenames without mutating the loaded analysis.
- Switching customization back to "NÃO" restores original input metadata for future exports.

### Compatibility

- Preserved graph calculations, ETL behavior, PDF layout, update workflow and benchmark methodology.
- Preserved collision-safe suffix behavior for duplicate or locked PDF filenames.

## v1.3.8

### New Features

- Added click-and-drag date range preparation in the SELECAO detected-days table.
- Added Shift-click inclusive range preparation in both SELECAO and custom export day tables.
- Added current-measurement export cancellation using the same cooperative cancellation flow used by custom export.

### Improvements

- Renamed the standard active-interval export action to EXPORTAR MEDICAO ATUAL.
- Refined the embedded custom export interval controls to match the SELECAO tab behavior.
- Standardized export completion, cancellation and error dialogs across all export modes.
- Preserved single-click day preparation and double-click apply behavior.
- Preserved active SELECAO interval behavior after custom export.

### Performance

- Optimized Primata TXT ETL by using safer fast paths for CSV parsing, datetime parsing and numeric dtype preservation.
- Added graph caching for already generated graphs with invalidation on file load, new analysis and interval changes.
- Added conservative parallel daily PDF export with two workers.
- Added release benchmark automation with JSON and Markdown outputs.
- v1.3.8 timing benchmark reference: ETL 1.946s; initial graph generation 1.432s; current measurement PDF export 1.974s; custom single PDF export 1.772s; custom daily PDF export 7.258s for seven daily PDFs using one graph.

### Bug Fixes

- Standardized PDF filenames using the "GR - EMPRESA - YYYYMMDD-HHMMSS - REV00.pdf" pattern.
- Added timestamps to all generated PDF filename patterns.
- Added safe filename de-duplication to avoid overwriting existing PDFs.
- Fixed custom daily PDF export filename collisions by precomputing unique output paths before launching parallel workers.
- Added retry with numeric suffixes when a target PDF path is already locked or unavailable.
- Prevented duplicate filename allocation inside the same parallel export batch.

### Benchmark Results

- Startup subprocess: 1.375s in timing-only benchmark.
- App import: 1.196s in timing-only benchmark.
- ETL: 1.946s in timing-only benchmark, approximately 68 percent faster than the prior 6.104s reference from the v1.3.8 pre-hardening benchmark.
- Daily PDF export: 7.258s in timing-only benchmark, approximately 35 percent faster than the prior 11.218s reference.
- Official memory benchmark uses tracemalloc fallback when psutil is unavailable.

### Known Limitations

- XLS validation depends on available customer samples; the release dataset set includes Primata XLSX, Primata TXT and Embrasul TXT.
- PDF export time still scales with graph count because each selected graph is rendered through Plotly/Kaleido.
- psutil is optional; RSS peak memory is reported only when psutil is installed.

## v1.3.7

- Replaced fixed daily PDF export with a custom measurement export workflow.
- Added a dedicated "EXPORTAR MEDIÇÃO PERSONALIZADA" dialog.
- Added export scopes for full measurement, custom interval and selected days.
- Added export modes for single PDF and PDFs separated by day.
- Added graph selection and output folder selection inside the custom export dialog.
- Added validation and summary preview before custom export.
- Added custom single PDF filename pattern "GR - EMPRESA - PERSONALIZADA - YYYYMMDD-HHMMSS.pdf".
- Preserved standard single PDF export behavior for the active SELECAO interval.

## v1.3.6

- Renamed the SELECAO day dropdown placeholder to Medicao Completa.
- Added gray highlighting for the full measurement prepared range.
- Added gray highlighting for prepared multi-day date ranges.
- Added daily PDF export using detected measurement days.
- Daily PDFs use each day's actual first and last measurement timestamp.
- Daily PDF export preserves the active applied interval after completion.
- Added cooperative cancellation for daily PDF export.
- Updated daily PDF filenames to the "GR - EMPRESA - YYYYMMDD.pdf" pattern.
- Kept single PDF export behavior and layout unchanged.

## v1.3.5

- Added SELECAO tab for global time interval selection.
- Added detected days table with complete/incomplete day status.
- Added measurement summary with period, duration and integration interval.
- Added measurement-date dropdowns and integration-based time dropdowns.
- Added quick time options for first/last record of the selected day.
- Added global filtering so all graph tabs and PDF export use the selected interval.
- Improved update workflow and direct installer download behavior.
- Improved update dialog wording.
- Improved PDF export preflight feedback.
- Fixed version display normalization to prevent duplicated "v" prefix.
