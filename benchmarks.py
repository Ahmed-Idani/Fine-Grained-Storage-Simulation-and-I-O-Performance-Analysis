import csv
import os
import subprocess
import time

import numpy as np

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from generate_data import generate_subrecords
from storage_strategies import (
    load_chunked_index,
    load_single_index,
    read_record_chunked,
    read_record_individual,
    read_record_single_file,
    write_chunked_files,
    write_individual_files,
    write_single_file,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")


def get_disk_io():
    if HAS_PSUTIL:
        c = psutil.disk_io_counters()
        return {"read_bytes": c.read_bytes, "write_bytes": c.write_bytes,
                "read_count": c.read_count, "write_count": c.write_count}
    return None


def get_cpu_percent():
    if HAS_PSUTIL:
        return psutil.cpu_percent(interval=None)
    return None


def count_syscalls(script_snippet):
    try:
        cmd = f"strace -c -e trace=read,write,open,openat,close,lseek -f python3 -c \"{script_snippet}\" 2>&1"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        lines = result.stderr.strip().split("\n") if result.stderr else result.stdout.strip().split("\n")
        syscalls = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 5 and parts[-1] in ("read", "write", "open", "openat", "close", "lseek"):
                syscalls[parts[-1]] = int(parts[3])
        return syscalls if syscalls else None
    except Exception:
        return None


def measure(func):
    if HAS_PSUTIL:
        psutil.cpu_percent(interval=None)

    disk_before = get_disk_io()
    start = time.perf_counter()
    result = func()
    elapsed = time.perf_counter() - start
    disk_after = get_disk_io()
    cpu = get_cpu_percent()

    io_stats = None
    if disk_before and disk_after:
        io_stats = {
            "read_bytes": disk_after["read_bytes"] - disk_before["read_bytes"],
            "write_bytes": disk_after["write_bytes"] - disk_before["write_bytes"],
            "read_ops": disk_after["read_count"] - disk_before["read_count"],
            "write_ops": disk_after["write_count"] - disk_before["write_count"],
        }

    return result, elapsed, cpu, io_stats


def fmt_bytes(b):
    if b is None:
        return "N/A"
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def run_benchmarks():
    print("=" * 70)
    print("DUNE Storage Benchmark — 100,000 sub-records (~150 MB)")
    print("=" * 70)

    if HAS_PSUTIL:
        print("  [psutil] CPU and disk I/O metrics enabled")
    else:
        print("  [psutil] Not installed — install with: pip install psutil")

    print("\n[1/7] Generating data...")
    records, gen_time, _, _ = measure(lambda: generate_subrecords(100_000, seed=42))
    print(f"  Data generated in {gen_time:.2f}s")

    results = []
    metrics = []
    n = len(records)

    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("\n[2/7] Write benchmark: Strategy A (single file)...")
    _, t, cpu, io = measure(lambda: write_single_file(records))
    results.append(("A-single", "write", n, t, t / n))
    metrics.append(("A-single", "write", cpu, io))
    print(f"  {t:.3f}s total, {t/n*1e6:.1f} us/record")

    print("[3/7] Write benchmark: Strategy B (chunked)...")
    _, t, cpu, io = measure(lambda: write_chunked_files(records))
    results.append(("B-chunked", "write", n, t, t / n))
    metrics.append(("B-chunked", "write", cpu, io))
    print(f"  {t:.3f}s total, {t/n*1e6:.1f} us/record")

    print("[4/7] Write benchmark: Strategy C (individual files)...")
    _, t, cpu, io = measure(lambda: write_individual_files(records))
    results.append(("C-individual", "write", n, t, t / n))
    metrics.append(("C-individual", "write", cpu, io))
    print(f"  {t:.3f}s total, {t/n*1e6:.1f} us/record")

    print("\n[5/7] Sequential read benchmarks...")

    idx_a = load_single_index()
    _, t, cpu, io = measure(lambda: [read_record_single_file(idx_a, i) for i in range(n)])
    results.append(("A-single", "seq-read", n, t, t / n))
    metrics.append(("A-single", "seq-read", cpu, io))
    print(f"  A: {t:.3f}s total, {t/n*1e6:.1f} us/record")

    idx_b = load_chunked_index()
    _, t, cpu, io = measure(lambda: [read_record_chunked(idx_b, i) for i in range(n)])
    results.append(("B-chunked", "seq-read", n, t, t / n))
    metrics.append(("B-chunked", "seq-read", cpu, io))
    print(f"  B: {t:.3f}s total, {t/n*1e6:.1f} us/record")

    _, t, cpu, io = measure(lambda: [read_record_individual(i) for i in range(n)])
    results.append(("C-individual", "seq-read", n, t, t / n))
    metrics.append(("C-individual", "seq-read", cpu, io))
    print(f"  C: {t:.3f}s total, {t/n*1e6:.1f} us/record")

    print("\n[6/7] Random read benchmarks (1000 records)...")
    rng = np.random.default_rng(42)
    random_ids = rng.integers(0, n, size=1000).tolist()

    _, t, cpu, io = measure(lambda: [read_record_single_file(idx_a, rid) for rid in random_ids])
    results.append(("A-single", "rand-read", 1000, t, t / 1000))
    metrics.append(("A-single", "rand-read", cpu, io))
    print(f"  A: {t:.4f}s total, {t/1000*1e6:.1f} us/record")

    _, t, cpu, io = measure(lambda: [read_record_chunked(idx_b, rid) for rid in random_ids])
    results.append(("B-chunked", "rand-read", 1000, t, t / 1000))
    metrics.append(("B-chunked", "rand-read", cpu, io))
    print(f"  B: {t:.4f}s total, {t/1000*1e6:.1f} us/record")

    _, t, cpu, io = measure(lambda: [read_record_individual(rid) for rid in random_ids])
    results.append(("C-individual", "rand-read", 1000, t, t / 1000))
    metrics.append(("C-individual", "rand-read", cpu, io))
    print(f"  C: {t:.4f}s total, {t/1000*1e6:.1f} us/record")

    print("\n[7/7] Saving results...")
    csv_path = os.path.join(RESULTS_DIR, "benchmark_results.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "strategy", "operation", "num_records", "total_seconds",
            "avg_latency_seconds", "cpu_percent",
            "disk_read_bytes", "disk_write_bytes", "disk_read_ops", "disk_write_ops",
        ])
        for i, (strategy, op, count, total, avg) in enumerate(results):
            m = metrics[i]
            io = m[3] if m[3] else {}
            writer.writerow([
                strategy, op, count, f"{total:.6f}", f"{avg:.9f}",
                f"{m[2]:.1f}" if m[2] is not None else "",
                io.get("read_bytes", ""),
                io.get("write_bytes", ""),
                io.get("read_ops", ""),
                io.get("write_ops", ""),
            ])
    print(f"  Results saved to {csv_path}")

    print("\n" + "=" * 70)
    print(f"{'Strategy':<16} {'Operation':<12} {'Records':>8} {'Total (s)':>10} {'Avg (us)':>10}")
    print("-" * 70)
    for strategy, op, count, total, avg in results:
        print(f"{strategy:<16} {op:<12} {count:>8,} {total:>10.3f} {avg*1e6:>10.1f}")
    print("=" * 70)

    if HAS_PSUTIL:
        print(f"\n{'Strategy':<16} {'Operation':<12} {'CPU %':>7} {'Disk Read':>12} {'Disk Write':>12} {'Read Ops':>10} {'Write Ops':>10}")
        print("-" * 90)
        for (strategy, op, cpu, io) in metrics:
            cpu_str = f"{cpu:.1f}" if cpu is not None else "N/A"
            if io:
                print(f"{strategy:<16} {op:<12} {cpu_str:>7} {fmt_bytes(io['read_bytes']):>12} {fmt_bytes(io['write_bytes']):>12} {io['read_ops']:>10,} {io['write_ops']:>10,}")
            else:
                print(f"{strategy:<16} {op:<12} {cpu_str:>7} {'N/A':>12} {'N/A':>12} {'N/A':>10} {'N/A':>10}")
        print("=" * 90)

    print("\n[Bonus] Counting syscalls with strace (Strategy A write, 1000 records)...")
    strace_script = (
        "from generate_data import generate_subrecords; "
        "from storage_strategies import write_single_file; "
        "records = generate_subrecords(1000, seed=42); "
        "write_single_file(records)"
    )
    syscalls = count_syscalls(strace_script)
    if syscalls:
        print("  Syscalls for Strategy A write (1000 records):")
        for name, count in sorted(syscalls.items()):
            print(f"    {name}: {count}")
    else:
        print("  strace not available or failed (requires Linux + permissions)")

    return results


if __name__ == "__main__":
    run_benchmarks()
