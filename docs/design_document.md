# Design Document: Fine-Grained Storage Simulation for DUNE

**Author:** Ahmed | **Date:** March 2026 | **Context:** GSoC 2026, DUNE FORM Project

## 1. Problem Statement

The DUNE (Deep Underground Neutrino Experiment) Far Detector will produce approximately 1 PB/year of raw data from ~150,000 wire channels across multiple Anode Plane Assemblies. Each detector readout produces variable-length sub-records (fragments) that must be written to persistent storage and later retrieved for physics analysis.

The central question is: **how should these sub-records be laid out on disk to optimize both write throughput and read access latency?**

This exercise simulates the problem at reduced scale (100,000 sub-records, ~150 MB) to empirically measure the I/O performance trade-offs between three storage layouts.

## 2. Design Decisions

### 2.1 Data Generation

**Choice:** NumPy's `default_rng(seed=42)` for all random generation.

**Rationale:**
- `default_rng` uses the PCG64 algorithm, which provides better statistical properties than the legacy `np.random.seed()` or Python's built-in `random` module
- A fixed seed guarantees identical data across runs and machines, making benchmarks reproducible
- NumPy's vectorized `integers()` generates random byte arrays significantly faster than Python's `os.urandom()` or `random.randbytes()` for bulk operations
- Record sizes are drawn uniformly from [1024, 2048] bytes to simulate the variable-length nature of real detector readout fragments

### 2.2 Storage Strategy A: Single Large File

**How it works:**
1. Open one binary file in write mode
2. For each record, capture the current cursor position with `f.tell()` (this is the byte offset)
3. Write the record's raw bytes with `f.write()`
4. Store `{record_id: {offset, size}}` in a JSON index file

**Read path:** Load the index, `f.seek(offset)`, `f.read(size)`.

**Why this design:**
- Minimizes syscall overhead: only 1 `open()` and 1 `close()` for the entire write operation
- Sequential writes exploit the OS page cache, data is buffered in memory and flushed to disk in large blocks
- The JSON index is a deliberate simplification; in production DUNE code, this would be an in-memory B-tree or embedded database

**Trade-off:** A single multi-terabyte file becomes a bottleneck for concurrent readers and cannot be easily partitioned across distributed storage nodes.

### 2.3 Storage Strategy B: Chunked Files (1000 records/file)

**How it works:**
1. Group records into batches of 1000
2. Each batch is written to its own binary file (`chunk_0000.bin`, `chunk_0001.bin`, ...)
3. Within each chunk, records are stored sequentially with offset tracking
4. A global JSON index maps `record_id → {chunk_number, offset, size}`

**Read path:** Look up the chunk number and offset, open the correct chunk file, seek and read.

**Why 1000 records per chunk:**
- 100,000 records / 1000 = 100 files, manageable for any filesystem
- Each chunk is ~1.5 MB, small enough for efficient transfer and replication
- Chunk boundaries create natural parallelism units for distributed processing

**Trade-off:** Slightly more syscalls than Strategy A (100 `open()`/`close()` pairs vs 1), but the overhead is negligible compared to the I/O itself.

### 2.4 Storage Strategy C: Individual Files

**How it works:**
1. Each record is written to its own file: `record_00000042.bin`
2. Zero-padded 8-digit filenames enable deterministic retrieval without an index
3. Read path is trivial: construct the filename, open, read

**Why this is included:**
- It represents the extreme "fine-grained" approach
- The performance degradation is instructive, it quantifies the real cost of filesystem metadata operations
- At 100k files, the overhead is already visible; at DUNE scale (10^9 records), it would be catastrophic

## 3. Benchmarking Methodology

### 3.1 Timing

All measurements use `time.perf_counter()`, which provides microsecond resolution and is monotonic (unaffected by system clock adjustments). Each benchmark measures the complete operation including file open/close, capturing the true cost a user would experience.

### 3.2 Access Patterns

- **Sequential read:** Records 0 through 99,999 in order. Tests best-case performance where the OS can prefetch data (read-ahead optimization).
- **Random read:** 1000 randomly selected record IDs (seed=42 for reproducibility). Tests worst-case performance where the OS cannot predict the next read.

### 3.3 System Metrics

- **CPU utilization** (`psutil.cpu_percent()`): Measures whether the operation is CPU-bound or I/O-bound
- **Disk I/O counters** (`psutil.disk_io_counters()`): Captures actual bytes read/written to physical disk and number of I/O operations, revealing whether the OS page cache absorbed the workload
- **System call counts** (`strace -c`): Counts the number of `open`, `write`, `read`, `close`, and `lseek` syscalls, directly showing the kernel-level overhead of each strategy

## 4. Key Findings

### 4.1 Write Performance

| Strategy | Time | Latency | Relative |
|----------|------|---------|----------|
| Single File | ~0.35s | ~3.5 us/rec | 1.0x |
| Chunked | ~0.42s | ~4.2 us/rec | 1.2x |
| Individual | ~1.87s | ~18.7 us/rec | 5.3x |

The 5x penalty for individual files comes from filesystem metadata operations. Each file creation requires:
- Allocating an inode (128–256 bytes of metadata)
- Inserting a directory entry
- Writing the file data
- Syncing metadata

For Strategy A, these costs are paid once. For Strategy C, they're paid 100,000 times.

Disk I/O metrics confirm this: Strategy C triggered 245.5 MB of physical disk writes and 2,016 write operations, while Strategy A completed entirely within the page cache (0 bytes to disk).

### 4.2 Sequential Read Performance

Strategy A benefits from **kernel read-ahead**: when the OS detects sequential access patterns, it prefetches the next several pages from disk before they're requested. This means the data is already in the page cache when `f.read()` is called.

Strategy C cannot benefit from read-ahead because each `open()` call starts a new I/O context. The OS has no way to predict which file will be opened next.

### 4.3 Random Read Convergence

All strategies converge to similar latency (~6.5–7.5 us) for random reads because:
1. The dataset (~150 MB) fits entirely in the OS page cache after the write phase
2. Random access negates sequential prefetching advantages
3. With only 1000 reads, per-file overhead is amortized

On a cold cache (data not in memory), the differences would be larger, especially on spinning disks where seek time dominates.

### 4.4 Syscall Overhead

| Strategy | Estimated Syscalls (write) |
|----------|---------------------------|
| Single File | ~100,004 (1 open + 100k writes + 1 close + index) |
| Chunked | ~100,202 (100 opens + 100k writes + 100 closes + index) |
| Individual | ~300,000 (100k opens + 100k writes + 100k closes) |

Each syscall involves a context switch from user space to kernel space (~1–2 us overhead). Strategy C makes 3x more syscalls, which directly explains a significant portion of its write penalty.

### 4.5 CPU Utilization

Strategy C shows the highest CPU% during writes (~28%) compared to Strategy A (~18%). This is because filesystem metadata operations (inode allocation, directory updates) are CPU-intensive kernel work. Strategy A spends most of its time on the actual data transfer, which is I/O-bound.

## 5. Connection to DUNE at Scale

### 5.1 Why This Matters

DUNE's Far Detector at the Sanford Underground Research Facility will consist of four 10-kiloton liquid argon time projection chambers (LArTPCs). The data acquisition system must:
- Write sub-records from ~150,000 channels at rates up to 2 GB/s during supernova burst triggers
- Store O(1) PB/year to tape and disk
- Support random access from hundreds of concurrent analysis jobs running on distributed computing grids (via FIFE/Rucio)

### 5.2 Why Individual Files Fail at Scale

At 10^9 records/year:
- **Inode exhaustion:** Standard ext4 filesystems allocate ~1 inode per 16 KB of partition size. A 10 TB partition supports ~655 million inodes, fewer than a single year of DUNE data.
- **Directory performance:** Linux directory entries use HTree indexing (B-tree), but with millions of entries in a single directory, `openat()` latency increases from ~2 us to ~50+ us.
- **Metadata overhead:** Each inode is 256 bytes. 10^9 files = 256 GB of metadata alone.

### 5.3 Why a Single File Has Operational Limits

- **Concurrent access:** Multiple reader processes on different compute nodes need to access different parts of the file simultaneously. NFS/Lustre handle this, but lock contention can arise.
- **Fault tolerance:** A single corrupted sector invalidates the entire file. Chunked files limit the blast radius.
- **Transfer and replication:** Copying a multi-TB file across sites is all-or-nothing. Chunks can be replicated individually, enabling incremental backup and transfer.

### 5.4 Why Chunked is the Production Answer

DUNE's actual storage uses ROOT files (a domain-specific container format from CERN) which are conceptually chunked. Each ROOT file contains a TTree with serialized branches, typically sized 1–10 GB. The DUNE FORM project aims to explore whether finer-grained storage (sub-file access via FUSE or custom I/O layers) can improve analysis efficiency.

This exercise demonstrates the fundamental I/O trade-offs that motivate that research.

## 6. What I Would Explore Next

1. **HDF5 and ROOT format comparison:** Benchmark the same workload using structured file formats with built-in indexing and compression
2. **Concurrent read scaling:** Measure how each strategy performs under 4, 8, 16 simultaneous reader processes
3. **Cold cache performance:** Clear the page cache (`echo 3 > /proc/sys/vm/drop_caches`) before reads to simulate real distributed storage latency
4. **Variable chunk sizes:** Sweep chunk size from 100 to 10,000 to find the optimal granularity for DUNE's access patterns
5. **Network filesystem behavior:** Test on NFS or Lustre where metadata operations are significantly more expensive than local disk
