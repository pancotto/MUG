# MUG Benchmark lazy-pdf-exporter

## Environment

- Dataset: `benchmarks\datasets\embrasul.txt`
- Rows: `15044`
- Columns: `71`
- Python: `3.12.9 (tags/v3.12.9:fdb8142, Feb  4 2025, 15:27:58) [MSC v.1942 64 bit (AMD64)]`
- Platform: `win32`

## Summary

| Metric | Seconds | Memory Delta |
|---|---:|---:|
| startup | 1.030 | n/a |
| etl | 1.405 | n/a |
| initial_graph_generation | 1.239 | n/a |
| zoom_rebuild | 0.716 | n/a |
| pdf_export | 21.093 | n/a |

## Graph Generation

| Graph | Seconds | Memory Delta |
|---|---:|---:|
| Tensao | 0.260 | n/a |
| Corrente | 0.065 | n/a |
| Potencia Ativa | 0.074 | n/a |
| Potencia Aparente | 0.057 | n/a |
| Fator de Potencia | 0.048 | n/a |
| Deseq. Tensao | 0.063 | n/a |
| Deseq. Corrente | 0.055 | n/a |
| Consumo | 0.045 | n/a |
| DHT Tensao | 0.065 | n/a |
| DHT Corrente | 0.061 | n/a |
| Tensao x Corrente | 0.167 | n/a |
| kW x kVA | 0.160 | n/a |

## Zoom Rebuild

| Graph | Seconds | Memory Delta |
|---|---:|---:|
| Tensao | 0.058 | n/a |
| Corrente | 0.059 | n/a |
| Potencia Ativa | 0.045 | n/a |
| Potencia Aparente | 0.052 | n/a |
| Fator de Potencia | 0.036 | n/a |
| Deseq. Tensao | 0.047 | n/a |
| Deseq. Corrente | 0.041 | n/a |
| Consumo | 0.033 | n/a |
| DHT Tensao | 0.052 | n/a |
| DHT Corrente | 0.048 | n/a |
| Tensao x Corrente | 0.117 | n/a |
| kW x kVA | 0.124 | n/a |

## PDF Export

| Graph | Build | Image | Page |
|---|---:|---:|---:|
| Tensão | 0.091 | 1.853 | 0.013 |
| Corrente | 0.142 | 1.635 | 0.016 |
| Potência Ativa | 0.110 | 1.560 | 0.020 |
| Potência Aparente | 0.093 | 1.535 | 0.023 |
| Fator de Potência | 0.084 | 1.519 | 0.017 |
| DHT Tensão | 0.107 | 1.637 | 0.017 |
| DHT Corrente | 0.102 | 1.685 | 0.017 |
| Deseq. Tensão | 0.099 | 1.644 | 0.016 |
| Deseq. Corrente | 0.077 | 1.538 | 0.028 |
| Consumo | 0.064 | 1.357 | 0.014 |
| Tensão x Corrente | 0.283 | 1.837 | 0.016 |
| kW x kVA | 0.222 | 1.569 | 0.022 |

## Artifacts

- JSON: `docs\benchmarks\runs\lazy-pdf-exporter.json`
- Markdown: `docs\benchmarks\runs\lazy-pdf-exporter.md`
- Log: `docs\benchmarks\logs\lazy-pdf-exporter.log`
- PDF: `C:\Users\eco98\VSCodeProjects\MUG\docs\benchmarks\artifacts\lazy-pdf-exporter\pdf\benchmark-export.pdf`

