# MUG Benchmarks

This directory stores reproducible benchmark results for MUG.

Run a benchmark from the project root:

```powershell
.venv\Scripts\python.exe scripts\benchmark_mug.py
```

Run with an explicit dataset:

```powershell
.venv\Scripts\python.exe scripts\benchmark_mug.py --dataset benchmarks\datasets\primata.xlsx
```

Compare two historical runs:

```powershell
.venv\Scripts\python.exe scripts\benchmark_compare.py docs\benchmarks\runs\baseline.json docs\benchmarks\latest.json
```

Generated files:

- `latest.json`: latest structured benchmark result.
- `latest.md`: latest human-readable benchmark report.
- `runs/*.json`: historical structured runs.
- `runs/*.md`: historical Markdown summaries.
- `logs/*.log`: benchmark and profiling logs.
- `artifacts/*`: generated PDFs and other benchmark artifacts.

The benchmark uses real project code and intentionally does not optimize or
change application behavior.
