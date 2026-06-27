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

## Benchmark provenance

For maintenance releases that only change UI, robustness or release-readiness behavior, benchmark values may be inherited from the latest applicable run when ETL, electrical calculations, graph formulas, PDF generation algorithms and filename standards are unchanged.

For v1.6.1, the published benchmark values are treated as inherited release-readiness evidence because the RC polishing work does not change measured processing or export algorithms. Refresh the benchmark after the final packaged build if a release manager wants commit-exact benchmark provenance.
