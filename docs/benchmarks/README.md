# Benchmark Workflow

Run release benchmarks with the generic release script:

```bash
python benchmarks/benchmark_release.py --version vX.Y.Z
```

The script writes:

- `docs/benchmarks/vX.Y.Z_benchmark.md`
- `docs/benchmarks/runs/vX.Y.Z.json`
- `docs/benchmarks/latest.md`
- `docs/benchmarks/latest.json`

By default, generated PDF artifacts are written to a temporary directory and removed after the run. To keep PDF artifacts for inspection, pass:

```bash
python benchmarks/benchmark_release.py --version vX.Y.Z --keep-artifacts
```

Use `--artifact-dir <path>` when a custom retained artifact location is needed.

Memory measurement uses `psutil` when available and falls back to `tracemalloc` when `psutil` is not installed.
