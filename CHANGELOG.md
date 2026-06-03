# Changelog

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
