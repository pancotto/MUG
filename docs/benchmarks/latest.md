# MUG Benchmark v1.3.3

- Created at: `2026-05-12T16:15:01`
- Scope: startup/import, ETL, graph generation, zoom/rebuild, phase sync, `(V) x (I)`, PDF, updater.
- Historical note: v1.3.2 benchmark file was not found; comparison uses v1.3.1 where available.

## v1.3.3 Summary

| Metric | Mean seconds |
|---|---:|
| startup_import_mean | 1.348 |
| etl_mean | 4.284 |
| initial_graph_generation_mean | 1.397 |
| zoom_rebuild_mean | 0.775 |
| pdf_export_mean | 100.168 |
| vxi_initial_mean | 0.216 |
| vxi_zoom_mean | 0.147 |
| vxi_pdf_build_mean | 0.257 |
| vxi_pdf_image_mean | 8.301 |

## Dataset Results

| Dataset | Startup | ETL | Initial Graphs | Zoom/Rebuild | PDF | VXI Initial | VXI Zoom | VXI PDF Build | VXI PDF Image |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| primata.xlsx | 2.029 | 10.094 | 1.492 | 0.782 | 98.505 | 0.233 | 0.166 | 0.284 | 8.196 |
| primata.txt | 0.940 | 2.042 | 1.381 | 0.785 | 106.055 | 0.222 | 0.157 | 0.265 | 8.775 |
| embrasul.txt | 1.075 | 0.715 | 1.319 | 0.757 | 95.944 | 0.194 | 0.118 | 0.221 | 7.933 |

## ETL Breakdown

| Dataset | Read | Datetime Parse | Numeric Parse | Prepare Common | Numeric Columns | Already Numeric | Parsed Numeric |
|---|---:|---:|---:|---:|---:|---:|---:|
| primata.xlsx | 10.261 | 0.059 | 0.020 | 0.107 | 62 | 62 | 0 |
| primata.txt | 0.482 | 0.069 | 1.413 | 1.488 | 62 | 0 | 62 |
| embrasul.txt | 0.561 | 0.029 | 0.010 | 0.050 | 68 | 68 | 0 |

## Phase Sync Incremental

| Metric | Mean ms | Min ms | Max ms |
|---|---:|---:|---:|
| hide_R | 6.045 | 5.645 | 7.293 |
| hide_S | 3.493 | 3.259 | 4.127 |
| reactivate_R | 6.083 | 5.706 | 6.614 |
| reactivate_S | 8.379 | 7.758 | 9.535 |
| only_T | 3.525 | 3.246 | 4.138 |
| all_visible | 8.596 | 7.965 | 9.502 |
| vxi_extreme_recalc_only_T | 1.185 | 1.049 | 1.465 |
| plotly_restyle_payload_build | 0.097 | 0.091 | 0.187 |
| updater_build_download_url | 0.000 | 0.000 | 0.007 |

## UI Startup / Updater

| Metric | Seconds |
|---|---:|
| ui_import_ui | 0.794 |
| ui_qapplication | 0.047 |
| ui_mainwindow_creation | 1.349 |
| ui_total_to_ui_ready | 2.190 |
| updater_get_latest_release | 0.425 |
| updater_is_update_available | 0.225 |
| updater_build_download_url | 0.000 |
| updater_latest_version | 1.3.3 |

## Historical Comparison v1.3.1 -> v1.3.3

| Dataset | Metric | v1.3.1 | v1.3.2 | v1.3.3 | Delta v1.3.3 vs v1.3.1 | Delta % |
|---|---|---:|---:|---:|---:|---:|
| primata.xlsx | startup | 1.498 | n/a | 2.029 | 0.531 | +35.4% |
| primata.xlsx | etl | 9.756 | n/a | 10.094 | 0.338 | +3.5% |
| primata.xlsx | initial_graph_generation | 1.377 | n/a | 1.492 | 0.116 | +8.4% |
| primata.xlsx | zoom_rebuild | 0.735 | n/a | 0.782 | 0.047 | +6.3% |
| primata.xlsx | pdf_export | n/a | n/a | 98.505 | n/a | n/a |
| primata.xlsx | vxi_initial | 0.209 | n/a | 0.233 | 0.024 | +11.5% |
| primata.xlsx | vxi_zoom | 0.153 | n/a | 0.166 | 0.014 | +8.9% |
| primata.xlsx | vxi_pdf_build | n/a | n/a | 0.284 | n/a | n/a |
| primata.xlsx | vxi_pdf_image | n/a | n/a | 8.196 | n/a | n/a |
| primata.txt | startup | 0.901 | n/a | 0.940 | 0.040 | +4.4% |
| primata.txt | etl | 2.020 | n/a | 2.042 | 0.022 | +1.1% |
| primata.txt | initial_graph_generation | 1.345 | n/a | 1.381 | 0.036 | +2.7% |
| primata.txt | zoom_rebuild | 0.808 | n/a | 0.785 | -0.022 | -2.8% |
| primata.txt | pdf_export | n/a | n/a | 106.055 | n/a | n/a |
| primata.txt | vxi_initial | 0.225 | n/a | 0.222 | -0.003 | -1.2% |
| primata.txt | vxi_zoom | 0.160 | n/a | 0.157 | -0.003 | -2.0% |
| primata.txt | vxi_pdf_build | n/a | n/a | 0.265 | n/a | n/a |
| primata.txt | vxi_pdf_image | n/a | n/a | 8.775 | n/a | n/a |
| embrasul.txt | startup | 0.812 | n/a | 1.075 | 0.263 | +32.4% |
| embrasul.txt | etl | 0.653 | n/a | 0.715 | 0.062 | +9.5% |
| embrasul.txt | initial_graph_generation | 1.057 | n/a | 1.319 | 0.263 | +24.8% |
| embrasul.txt | zoom_rebuild | 0.647 | n/a | 0.757 | 0.109 | +16.9% |
| embrasul.txt | pdf_export | 95.127 | n/a | 95.944 | 0.817 | +0.9% |
| embrasul.txt | vxi_initial | 0.145 | n/a | 0.194 | 0.048 | +33.3% |
| embrasul.txt | vxi_zoom | 0.117 | n/a | 0.118 | 0.001 | +0.8% |
| embrasul.txt | vxi_pdf_build | 0.198 | n/a | 0.221 | 0.023 | +11.7% |
| embrasul.txt | vxi_pdf_image | 7.916 | n/a | 7.933 | 0.017 | +0.2% |

## Technical Analysis

- The dominant current bottleneck is PDF rendering through Kaleido/image export, not graph construction or phase sync.
- `(V) x (I)` integration adds small Python-side overhead: initial VXI build remains around 0.19-0.23s, zoom build around 0.12-0.17s, and VXI extreme recalculation around 1.2ms.
- Global phase sync is incremental: the benchmark measured state propagation, figure visibility updates, extreme recalculation, and restyle payload generation without full graph rebuild.
- ETL remains format-dependent: Primata XLSX is dominated by physical/openpyxl read; Primata TXT is dominated by numeric parsing; Embrasul TXT is already mostly numeric after conversion and stays very fast.
- Updater direct URL construction is effectively free; real GitHub API check measured around a few hundred milliseconds and is not loaded during pure app import.

## Artifacts

- `docs/benchmarks/runs/v1.3.3-primata-xlsx.json`
- `docs/benchmarks/runs/v1.3.3-primata-txt.json`
- `docs/benchmarks/runs/v1.3.3-embrasul.json`
- `docs/benchmarks/runs/v1.3.3-phase-sync-updater.json`
- `docs/benchmarks/runs/v1.3.3-ui-startup.json`
- `docs/benchmarks/runs/v1.3.3-etl-breakdown.json`
- `docs/benchmarks/runs/v1.3.3-updater-network.json`
