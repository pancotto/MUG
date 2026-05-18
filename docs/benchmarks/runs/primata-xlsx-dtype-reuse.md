# MUG Benchmark primata-xlsx-dtype-reuse

## Environment

- Dataset: `benchmarks\datasets\primata.xlsx`
- Rows: `33603`
- Columns: `65`
- Python: `3.12.9 (tags/v3.12.9:fdb8142, Feb  4 2025, 15:27:58) [MSC v.1942 64 bit (AMD64)]`
- Platform: `win32`

## Summary

| Metric | Seconds | Memory Delta |
|---|---:|---:|
| startup | 20.591 | n/a |
| etl | 9.805 | n/a |
| initial_graph_generation | 1.342 | n/a |
| zoom_rebuild | 0.745 | n/a |

## Graph Generation

| Graph | Seconds | Memory Delta |
|---|---:|---:|
| Tensao | 0.261 | n/a |
| Corrente | 0.083 | n/a |
| Potencia Ativa | 0.060 | n/a |
| Potencia Aparente | 0.081 | n/a |
| Fator de Potencia | 0.058 | n/a |
| Deseq. Tensao | 0.060 | n/a |
| Deseq. Corrente | 0.053 | n/a |
| Consumo | 0.048 | n/a |
| DHT Tensao | 0.072 | n/a |
| DHT Corrente | 0.074 | n/a |
| Tensao x Corrente | 0.213 | n/a |
| kW x kVA | 0.179 | n/a |

## Zoom Rebuild

| Graph | Seconds | Memory Delta |
|---|---:|---:|
| Tensao | 0.079 | n/a |
| Corrente | 0.056 | n/a |
| Potencia Ativa | 0.044 | n/a |
| Potencia Aparente | 0.044 | n/a |
| Fator de Potencia | 0.039 | n/a |
| Deseq. Tensao | 0.044 | n/a |
| Deseq. Corrente | 0.039 | n/a |
| Consumo | 0.032 | n/a |
| DHT Tensao | 0.054 | n/a |
| DHT Corrente | 0.050 | n/a |
| Tensao x Corrente | 0.154 | n/a |
| kW x kVA | 0.106 | n/a |

## PDF Export

| Graph | Build | Image | Page |
|---|---:|---:|---:|

## Artifacts

- JSON: `docs\benchmarks\runs\primata-xlsx-dtype-reuse.json`
- Markdown: `docs\benchmarks\runs\primata-xlsx-dtype-reuse.md`
- Log: `docs\benchmarks\logs\primata-xlsx-dtype-reuse.log`
- PDF: `n/a`

