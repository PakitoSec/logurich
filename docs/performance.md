# Performance reference

`scripts/benchmark_logging.py` is a dependency-free smoke benchmark for the v1
logging paths. Run it from the repository root:

```bash
uv run python scripts/benchmark_logging.py
```

Reference run on Python 3.11.13 (2026-08-01):

| Scenario | Time per call |
|---|---:|
| filtered DEBUG | 0.56 µs |
| plain INFO | 65.31 µs |
| INFO with two context values | 80.11 µs |
| live Panel and Table | 789.25 µs |
| plain exception | 147.66 µs |
| Rich exception | 4,108.87 µs |
| queued INFO submission | 14.68 µs |

These figures are diagnostic rather than portable limits: Rich rendering and
thread scheduling depend heavily on the host. Before the final v1 release, a
repeatable run on the same CI runner should stay within 25% of its rolling
baseline for the filtered, plain, context, and queue paths. A larger change must
be explained by a functional or output-quality improvement rather than accepted
without investigation.
