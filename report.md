# Fine-Grained Storage Simulation and I/O Performance Analysis for DUNE Sub-Record Data

**Author:** Ahmed | **Date:** 2026-03-05 | **Context:** GSoC 2026 Warm-Up Exercise

## 1. Abstract

This report evaluates three storage layout strategies for persisting variable-length sub-records representative of DUNE Far Detector readout fragments. We generated N = 100,000 synthetic sub-records (uniform size distribution in [1024, 2048] bytes, total volume ~150 MB) and measured write throughput, sequential read latency, and random-access latency for each strategy. Results indicate that a single contiguous file minimizes per-record I/O cost, while a chunked layout (1,000 records/file) provides a favorable trade-off between performance and operational scalability.

## 2. Experimental Setup

- **Data:** 100,000 sub-records, sizes drawn uniformly from [1024, 2048] bytes (seed = 42)
- **Platform:** Linux 6.17.0, ext4 filesystem, NVMe SSD
- **Timing:** `time.perf_counter()` (microsecond resolution), with CPU and disk I/O metrics via `psutil`
- **Strategies tested:**
  - **(A) Single file** — all records written sequentially to one binary blob; JSON offset index
  - **(B) Chunked files** — records grouped into files of 1,000; per-chunk offset index
  - **(C) Individual files** — one file per record; filename-based addressing

## 3. Results

|                  | Write              | Sequential Read    | Random Read (n=1000) |
|------------------|--------------------|--------------------|----------------------|
| Single File      | 0.387 s (3.9 us/rec)  | 0.563 s (5.6 us/rec)  | 0.008 s (8.0 us/rec)    |
| Chunked          | 0.419 s (4.2 us/rec)  | 0.655 s (6.5 us/rec)  | 0.008 s (8.2 us/rec)    |
| Individual Files | 1.855 s (18.6 us/rec) | 0.749 s (7.5 us/rec)  | 0.009 s (9.0 us/rec)    |

*Table 1. Total wall-clock time and mean per-record latency for each strategy and access pattern.*

![Write Throughput](results/plots/write_throughput.png)
![Read Latency](results/plots/read_latency.png)
![Summary Heatmap](results/plots/summary_heatmap.png)
![Syscall Comparison](results/plots/syscall_comparison.png)
![CPU Utilization](results/plots/cpu_utilization.png)
![Disk I/O](results/plots/disk_io.png)

## 4. Analysis

### 4.1 Write Throughput

The single-file strategy (A) achieves the lowest write latency at 3.9 us/record, attributable to a single `open()` syscall and sequential `write()` appends that exploit OS page-cache buffering. The chunked strategy (B) incurs an 8% overhead (4.2 us/record) from opening 100 chunk files. The individual-file strategy (C) exhibits a ~5x degradation (18.6 us/record), dominated by per-file filesystem metadata operations (inode allocation, directory entry insertion). System-level metrics confirm this: Strategy C generated 238 MB of disk writes and ~2,000 write I/O operations, while A and B completed entirely within the page cache.

### 4.2 Sequential Read Latency

Under sequential access (records 0 through 99,999 in order), strategy A benefits from kernel read-ahead prefetching, yielding 5.6 us/record. Strategy B is 16% slower (6.5 us/record) due to file-boundary transitions every 1,000 records. Strategy C narrows the gap to 34% slower (7.5 us/record), as the OS directory cache mitigates repeated `open()`/`close()` overhead for pre-existing files.

### 4.3 Random Access Latency

For a uniformly random sample of 1,000 record IDs, all three strategies converge: A at 8.0 us/record, B at 8.2 us/record, and C at 9.0 us/record. The elimination of sequential locality negates read-ahead benefits for strategy A, while the small sample size (1,000 operations) amortizes the fixed overhead of strategies B and C.

## 5. Discussion: Implications for DUNE

The DUNE Far Detector is projected to generate O(1) PB/year of raw data, comprising variable-length sub-records from ~150,000 wire channels across multiple Anode Plane Assemblies. At this scale:

- **Strategy C is infeasible.** Storing 10^9 records as individual files would exhaust inode tables and degrade directory lookup to O(n) on most filesystems. The ~5x write penalty observed at 100k records would compound further due to filesystem fragmentation.
- **Strategy A is optimal for throughput but operationally brittle.** A single multi-terabyte file creates a single point of failure, complicates concurrent read access from distributed computing jobs, and cannot be easily partitioned across storage nodes.
- **Strategy B offers the best scalability profile.** Chunked files reduce the file count by two orders of magnitude relative to C while maintaining near-optimal sequential write throughput. Chunk boundaries provide natural parallelism units for distributed processing frameworks (e.g., FIFE, Rucio), and individual chunk files can be replicated independently.

## 6. Conclusion

A chunked storage layout with ~1,000 records per file is recommended for DUNE sub-record persistence. It achieves write performance within 8% of the theoretical optimum (single file), maintains manageable file counts for filesystem scalability, and provides natural granularity for distributed I/O, replication, and concurrent access patterns characteristic of large-scale HEP data processing.
