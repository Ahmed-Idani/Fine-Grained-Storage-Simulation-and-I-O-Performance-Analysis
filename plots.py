import csv
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
PLOTS_DIR = os.path.join(RESULTS_DIR, "plots")
CSV_PATH = os.path.join(RESULTS_DIR, "benchmark_results.csv")

STRATEGIES = ["A-single", "B-chunked", "C-individual"]
LABELS = ["Single File", "Chunked", "Individual"]
STRATEGY_COLORS = ["#2196F3", "#4CAF50", "#FF9800"]


def load_results():
    data = defaultdict(dict)
    with open(CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry = {
                "total": float(row["total_seconds"]),
                "avg": float(row["avg_latency_seconds"]),
                "count": int(row["num_records"]),
            }
            if row.get("cpu_percent") and row["cpu_percent"]:
                entry["cpu"] = float(row["cpu_percent"])
            if row.get("disk_read_bytes") and row["disk_read_bytes"]:
                entry["disk_read_bytes"] = int(row["disk_read_bytes"])
            if row.get("disk_write_bytes") and row["disk_write_bytes"]:
                entry["disk_write_bytes"] = int(row["disk_write_bytes"])
            if row.get("disk_read_ops") and row["disk_read_ops"]:
                entry["disk_read_ops"] = int(row["disk_read_ops"])
            if row.get("disk_write_ops") and row["disk_write_ops"]:
                entry["disk_write_ops"] = int(row["disk_write_ops"])
            data[row["operation"]][row["strategy"]] = entry
    return data


def save(fig, name):
    fig.savefig(os.path.join(PLOTS_DIR, name), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {name}")


def plot_write_throughput(data):
    times = [data["write"][s]["total"] for s in STRATEGIES]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(LABELS, times, color=STRATEGY_COLORS, edgecolor="black", linewidth=0.5)
    for bar, t in zip(bars, times):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f"{t:.3f}s", ha="center", va="bottom", fontsize=11)
    ax.set_ylabel("Wall-clock time (seconds)")
    ax.set_title("Write Throughput — 100k records (~150 MB)")
    ax.set_ylim(0, max(times) * 1.25)
    fig.tight_layout()
    save(fig, "write_throughput.png")


def plot_read_latency(data):
    seq = [data["seq-read"][s]["avg"] * 1e6 for s in STRATEGIES]
    rand = [data["rand-read"][s]["avg"] * 1e6 for s in STRATEGIES]

    x = np.arange(len(LABELS))
    width = 0.35

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width / 2, seq, width, label="Sequential", color="#2196F3", edgecolor="black", linewidth=0.5)
    ax.bar(x + width / 2, rand, width, label="Random", color="#E91E63", edgecolor="black", linewidth=0.5)

    for i, (s, r) in enumerate(zip(seq, rand)):
        ax.text(i - width / 2, s + 0.2, f"{s:.1f}", ha="center", va="bottom", fontsize=9)
        ax.text(i + width / 2, r + 0.2, f"{r:.1f}", ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("Average latency (us/record)")
    ax.set_title("Read Latency — Sequential vs Random Access")
    ax.set_xticks(x)
    ax.set_xticklabels(LABELS)
    ax.legend()
    ax.set_ylim(0, max(max(seq), max(rand)) * 1.3)
    fig.tight_layout()
    save(fig, "read_latency.png")


def plot_summary_heatmap(data):
    operations = ["write", "seq-read", "rand-read"]
    labels_o = ["Write", "Seq Read", "Rand Read"]

    matrix = np.array([
        [data[op][s]["avg"] * 1e6 for op in operations]
        for s in STRATEGIES
    ])

    fig, ax = plt.subplots(figsize=(7, 4))
    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(len(labels_o)))
    ax.set_xticklabels(labels_o)
    ax.set_yticks(range(len(LABELS)))
    ax.set_yticklabels(LABELS)

    for i in range(len(LABELS)):
        for j in range(len(labels_o)):
            ax.text(j, i, f"{matrix[i, j]:.1f}", ha="center", va="center",
                    color="white" if matrix[i, j] > matrix.max() * 0.6 else "black", fontsize=11)

    ax.set_title("Average Latency (us/record)")
    fig.colorbar(im, ax=ax, label="us/record")
    fig.tight_layout()
    save(fig, "summary_heatmap.png")


def plot_syscall_comparison():
    syscalls = [100_004, 100_202, 300_000]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(LABELS, syscalls, color=STRATEGY_COLORS, edgecolor="black", linewidth=0.5)
    for bar, s in zip(bars, syscalls):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 3000,
                f"{s:,}", ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("Estimated syscalls (write operation)")
    ax.set_title("System Call Overhead — Write 100k Records")
    ax.set_ylim(0, max(syscalls) * 1.2)
    fig.tight_layout()
    save(fig, "syscall_comparison.png")


def plot_cpu_utilization(data):
    operations = ["write", "seq-read", "rand-read"]
    op_labels = ["Write", "Seq Read", "Rand Read"]

    has_cpu = any("cpu" in data[op].get(s, {}) for op in operations for s in STRATEGIES)
    if not has_cpu:
        print("  Skipping cpu_utilization.png (no psutil data)")
        return

    x = np.arange(len(LABELS))
    width = 0.25
    op_colors = ["#F44336", "#2196F3", "#E91E63"]

    fig, ax = plt.subplots(figsize=(10, 5))
    for j, (op, op_label, color) in enumerate(zip(operations, op_labels, op_colors)):
        vals = [data[op][s].get("cpu", 0) for s in STRATEGIES]
        ax.bar(x + j * width - width, vals, width, label=op_label, color=color, edgecolor="black", linewidth=0.5)

    ax.set_ylabel("CPU Utilization (%)")
    ax.set_title("CPU Utilization by Strategy and Operation")
    ax.set_xticks(x)
    ax.set_xticklabels(LABELS)
    ax.legend()
    fig.tight_layout()
    save(fig, "cpu_utilization.png")


def plot_disk_io(data):
    has_data = any("disk_write_bytes" in data["write"].get(s, {}) for s in STRATEGIES)
    if not has_data:
        print("  Skipping disk_io.png (no psutil data)")
        return

    write_mb = [data["write"][s].get("disk_write_bytes", 0) / 1e6 for s in STRATEGIES]
    write_ops = [data["write"][s].get("disk_write_ops", 0) for s in STRATEGIES]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    bars1 = ax1.bar(LABELS, write_mb, color=STRATEGY_COLORS, edgecolor="black", linewidth=0.5)
    for bar, v in zip(bars1, write_mb):
        label = f"{v:.1f} MB" if v > 0 else "0 MB\n(page cached)"
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(max(write_mb), 1) * 0.03,
                 label, ha="center", va="bottom", fontsize=10)
    ax1.set_ylabel("Bytes written to physical disk (MB)")
    ax1.set_title("Physical Disk Writes")
    ax1.set_ylim(0, max(max(write_mb), 1) * 1.25)

    bars2 = ax2.bar(LABELS, write_ops, color=STRATEGY_COLORS, edgecolor="black", linewidth=0.5)
    for bar, v in zip(bars2, write_ops):
        label = f"{v:,}" if v > 0 else "0\n(page cached)"
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(max(write_ops), 1) * 0.03,
                 label, ha="center", va="bottom", fontsize=10)
    ax2.set_ylabel("Write I/O operations")
    ax2.set_title("Disk Write Operations")
    ax2.set_ylim(0, max(max(write_ops), 1) * 1.25)

    fig.suptitle("Disk I/O During Write Phase (100k records)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    save(fig, "disk_io.png")


if __name__ == "__main__":
    os.makedirs(PLOTS_DIR, exist_ok=True)
    print("Loading results from", CSV_PATH)
    data = load_results()
    print("Generating plots...")
    plot_write_throughput(data)
    plot_read_latency(data)
    plot_summary_heatmap(data)
    plot_syscall_comparison()
    plot_cpu_utilization(data)
    plot_disk_io(data)
    print("Done!")
