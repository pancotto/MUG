# Benchmark Datasets

Place representative real or anonymized MUG input files in this directory.

The benchmark runner automatically searches for datasets in this order:

1. `primata.xlsx`
2. `primata.txt`
3. `embrasul.txt`

You can also pass a dataset explicitly:

```powershell
.venv\Scripts\python.exe scripts\benchmark_mug.py --dataset benchmarks\datasets\primata.xlsx
```

Keep datasets stable when comparing performance across commits. Hardware,
Windows background load, antivirus activity, and Chrome/Kaleido cache state can
affect timings, so compare repeated runs when possible.
