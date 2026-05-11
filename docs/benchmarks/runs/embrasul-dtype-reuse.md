# MUG Benchmark embrasul-dtype-reuse

## Environment

- Dataset: `benchmarks\datasets\embrasul.txt`
- Rows: `15044`
- Columns: `71`
- Python: `3.12.9 (tags/v3.12.9:fdb8142, Feb  4 2025, 15:27:58) [MSC v.1942 64 bit (AMD64)]`
- Platform: `win32`

## Summary

| Metric | Seconds | Memory Delta |
|---|---:|---:|
| startup | 2.250 | n/a |
| etl | 0.747 | n/a |
| initial_graph_generation | 1.548 | n/a |
| zoom_rebuild | 0.689 | n/a |

## Graph Generation

| Graph | Seconds | Memory Delta |
|---|---:|---:|
| Tensao | 0.482 | n/a |
| Corrente | 0.066 | n/a |
| Potencia Ativa | 0.077 | n/a |
| Potencia Aparente | 0.051 | n/a |
| Fator de Potencia | 0.043 | n/a |
| Deseq. Tensao | 0.053 | n/a |
| Deseq. Corrente | 0.047 | n/a |
| Consumo | 0.045 | n/a |
| DHT Tensao | 0.060 | n/a |
| DHT Corrente | 0.057 | n/a |
| Tensao x Corrente | 0.155 | n/a |
| kW x kVA | 0.132 | n/a |

## Zoom Rebuild

| Graph | Seconds | Memory Delta |
|---|---:|---:|
| Tensao | 0.054 | n/a |
| Corrente | 0.053 | n/a |
| Potencia Ativa | 0.042 | n/a |
| Potencia Aparente | 0.043 | n/a |
| Fator de Potencia | 0.031 | n/a |
| Deseq. Tensao | 0.043 | n/a |
| Deseq. Corrente | 0.038 | n/a |
| Consumo | 0.031 | n/a |
| DHT Tensao | 0.075 | n/a |
| DHT Corrente | 0.048 | n/a |
| Tensao x Corrente | 0.122 | n/a |
| kW x kVA | 0.105 | n/a |

## PDF Export

| Graph | Build | Image | Page |
|---|---:|---:|---:|

## Artifacts

- JSON: `docs\benchmarks\runs\embrasul-dtype-reuse.json`
- Markdown: `docs\benchmarks\runs\embrasul-dtype-reuse.md`
- Log: `docs\benchmarks\logs\embrasul-dtype-reuse.log`
- PDF: `n/a`

