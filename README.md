# DUNE Fine-Grained Storage Simulation

GSoC 2026 warm-up exercise — I/O performance analysis for the DUNE experiment.

## Requirements

- Python 3.8+
- Linux (for `strace` syscall counting)

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
source .venv/bin/activate

python3 run_all.py    # Full benchmark pipeline
python3 plots.py      # Generate plots from results
```

## Output

- `results/benchmark_results.csv` — raw timing and system metrics
- `results/plots/` — write throughput, read latency, heatmap, syscall, CPU, disk I/O charts
- `report.md` — 1-page scientific summary
- `docs/design_document.md` — detailed design rationale and DUNE context

## Project Structure

```
├── generate_data.py        # Step 1: Generate 100k sub-records (seed=42)
├── storage_strategies.py   # Step 2: Three storage layouts (single/chunked/individual)
├── benchmarks.py           # Steps 3-4: Timing, CPU, disk I/O, syscall measurement
├── plots.py                # Visualization (matplotlib)
├── run_all.py              # Entry point
├── report.md               # 1-page benchmark report
├── docs/
│   └── design_document.md  # Design rationale and DUNE context
├── requirements.txt        # numpy, matplotlib, psutil
└── results/                # Auto-generated benchmark data and plots
```
