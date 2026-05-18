# MUG Benchmark lazy-update-checker

## Environment

- Dataset: `benchmarks\datasets\embrasul.txt`
- Rows: `15044`
- Columns: `71`
- Python: `3.12.9 (tags/v3.12.9:fdb8142, Feb  4 2025, 15:27:58) [MSC v.1942 64 bit (AMD64)]`
- Platform: `win32`

## Summary

| Metric | Seconds | Memory Delta |
|---|---:|---:|
| startup | 0.899 | n/a |
| etl | 1.556 | n/a |
| initial_graph_generation | 1.260 | n/a |
| zoom_rebuild | 0.706 | n/a |
| pdf_export | 21.074 | n/a |

## Graph Generation

| Graph | Seconds | Memory Delta |
|---|---:|---:|
| Tensao | 0.255 | n/a |
| Corrente | 0.068 | n/a |
| Potencia Ativa | 0.092 | n/a |
| Potencia Aparente | 0.062 | n/a |
| Fator de Potencia | 0.049 | n/a |
| Deseq. Tensao | 0.051 | n/a |
| Deseq. Corrente | 0.046 | n/a |
| Consumo | 0.040 | n/a |
| DHT Tensao | 0.062 | n/a |
| DHT Corrente | 0.067 | n/a |
| Tensao x Corrente | 0.162 | n/a |
| kW x kVA | 0.168 | n/a |

## Zoom Rebuild

| Graph | Seconds | Memory Delta |
|---|---:|---:|
| Tensao | 0.064 | n/a |
| Corrente | 0.051 | n/a |
| Potencia Ativa | 0.042 | n/a |
| Potencia Aparente | 0.043 | n/a |
| Fator de Potencia | 0.032 | n/a |
| Deseq. Tensao | 0.047 | n/a |
| Deseq. Corrente | 0.037 | n/a |
| Consumo | 0.029 | n/a |
| DHT Tensao | 0.048 | n/a |
| DHT Corrente | 0.046 | n/a |
| Tensao x Corrente | 0.133 | n/a |
| kW x kVA | 0.129 | n/a |

## PDF Export

| Graph | Build | Image | Page |
|---|---:|---:|---:|
| Tensão | 0.093 | 1.756 | 0.039 |
| Corrente | 0.216 | 1.671 | 0.017 |
| Potência Ativa | 0.108 | 1.574 | 0.011 |
| Potência Aparente | 0.116 | 1.538 | 0.015 |
| Fator de Potência | 0.091 | 1.520 | 0.016 |
| DHT Tensão | 0.124 | 1.696 | 0.019 |
| DHT Corrente | 0.103 | 1.682 | 0.015 |
| Deseq. Tensão | 0.111 | 1.606 | 0.016 |
| Deseq. Corrente | 0.075 | 1.477 | 0.014 |
| Consumo | 0.054 | 1.356 | 0.015 |
| Tensão x Corrente | 0.235 | 1.903 | 0.015 |
| kW x kVA | 0.170 | 1.563 | 0.015 |

## Artifacts

- JSON: `docs\benchmarks\runs\lazy-update-checker.json`
- Markdown: `docs\benchmarks\runs\lazy-update-checker.md`
- Log: `docs\benchmarks\logs\lazy-update-checker.log`
- PDF: `C:\Users\eco98\VSCodeProjects\MUG\docs\benchmarks\artifacts\lazy-update-checker\pdf\benchmark-export.pdf`

