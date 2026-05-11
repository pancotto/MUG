# MUG Benchmark baseline

## Environment

- Dataset: `benchmarks\datasets\embrasul.txt`
- Rows: `15044`
- Columns: `71`
- Python: `3.12.9 (tags/v3.12.9:fdb8142, Feb  4 2025, 15:27:58) [MSC v.1942 64 bit (AMD64)]`
- Platform: `win32`

## Summary

| Metric | Seconds | Memory Delta |
|---|---:|---:|
| startup | 23.240 | n/a |
| etl | 1.420 | n/a |
| initial_graph_generation | 1.250 | n/a |
| zoom_rebuild | 0.668 | n/a |
| pdf_export | 20.549 | n/a |

## Graph Generation

| Graph | Seconds | Memory Delta |
|---|---:|---:|
| Tensao | 0.330 | n/a |
| Corrente | 0.067 | n/a |
| Potencia Ativa | 0.071 | n/a |
| Potencia Aparente | 0.053 | n/a |
| Fator de Potencia | 0.045 | n/a |
| Deseq. Tensao | 0.052 | n/a |
| Deseq. Corrente | 0.049 | n/a |
| Consumo | 0.048 | n/a |
| DHT Tensao | 0.060 | n/a |
| DHT Corrente | 0.061 | n/a |
| Tensao x Corrente | 0.149 | n/a |
| kW x kVA | 0.149 | n/a |

## Zoom Rebuild

| Graph | Seconds | Memory Delta |
|---|---:|---:|
| Tensao | 0.052 | n/a |
| Corrente | 0.052 | n/a |
| Potencia Ativa | 0.042 | n/a |
| Potencia Aparente | 0.043 | n/a |
| Fator de Potencia | 0.031 | n/a |
| Deseq. Tensao | 0.041 | n/a |
| Deseq. Corrente | 0.036 | n/a |
| Consumo | 0.031 | n/a |
| DHT Tensao | 0.050 | n/a |
| DHT Corrente | 0.044 | n/a |
| Tensao x Corrente | 0.116 | n/a |
| kW x kVA | 0.125 | n/a |

## PDF Export

| Graph | Build | Image | Page |
|---|---:|---:|---:|
| Tensão | 0.091 | 2.034 | 0.016 |
| Corrente | 0.129 | 1.652 | 0.017 |
| Potência Ativa | 0.081 | 1.562 | 0.013 |
| Potência Aparente | 0.079 | 1.503 | 0.019 |
| Fator de Potência | 0.071 | 1.430 | 0.014 |
| DHT Tensão | 0.086 | 1.673 | 0.013 |
| DHT Corrente | 0.089 | 1.610 | 0.033 |
| Deseq. Tensão | 0.079 | 1.497 | 0.011 |
| Deseq. Corrente | 0.075 | 1.503 | 0.013 |
| Consumo | 0.042 | 1.324 | 0.016 |
| Tensão x Corrente | 0.213 | 1.816 | 0.014 |
| kW x kVA | 0.163 | 1.517 | 0.014 |

## Artifacts

- JSON: `docs\benchmarks\runs\baseline.json`
- Markdown: `docs\benchmarks\runs\baseline.md`
- Log: `docs\benchmarks\logs\baseline.log`
- PDF: `C:\Users\eco98\VSCodeProjects\MUG\docs\benchmarks\artifacts\baseline\pdf\benchmark-export.pdf`

