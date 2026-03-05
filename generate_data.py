import numpy as np


def generate_subrecords(n=100_000, seed=42):
    rng = np.random.default_rng(seed)
    records = []
    for i in range(n):
        size = int(rng.integers(1024, 2049))
        data = rng.integers(0, 256, size=size, dtype=np.uint8).tobytes()
        records.append({"id": i, "size": size, "data": data})
    return records


def print_summary(records):
    total_bytes = sum(r["size"] for r in records)
    print(f"Generated {len(records):,} sub-records")
    print(f"Total data volume: {total_bytes / 1e6:.1f} MB")
    print(f"Average record size: {total_bytes / len(records):.1f} bytes")
    print()
    print("First 3 records:")
    for r in records[:3]:
        print(f"  id={r['id']}, size={r['size']}, first 8 bytes={r['data'][:8].hex()}")


if __name__ == "__main__":
    records = generate_subrecords()
    print_summary(records)
