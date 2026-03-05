"""
Three different approaches to writing and reading sub-records on disk.
"""

import json
import os
import shutil



# Strategy A - Single Large File

SINGLE_FILE_PATH = "results/strategy_a.bin"
SINGLE_INDEX_PATH = "results/strategy_a_index.json"


def write_single_file(records):
    """Write all records sequentially into one binary file + a JSON index."""
    index = {}
    with open(SINGLE_FILE_PATH, "wb") as f:
        for r in records:
            offset = f.tell()
            f.write(r["data"])
            index[r["id"]] = {"offset": offset, "size": r["size"]}
    with open(SINGLE_INDEX_PATH, "w") as f:
        json.dump(index, f)
    return index


def load_single_index():
    with open(SINGLE_INDEX_PATH, "r") as f:
        raw = json.load(f)
    return {int(k): v for k, v in raw.items()}


def read_record_single_file(index, record_id):
    """Read a single record from the large binary file using seek."""
    entry = index[record_id]
    with open(SINGLE_FILE_PATH, "rb") as f:
        f.seek(entry["offset"])
        return f.read(entry["size"])


# Strategy B - Chunked Files

CHUNK_DIR = "results/strategy_b_chunks"
CHUNK_INDEX_PATH = "results/strategy_b_index.json"
CHUNK_SIZE = 1000


def write_chunked_files(records):
    """Write records into chunk files of 1000 records each + a JSON index."""
    if os.path.exists(CHUNK_DIR):
        shutil.rmtree(CHUNK_DIR)
    os.makedirs(CHUNK_DIR, exist_ok=True)

    index = {}
    for chunk_num in range(0, len(records), CHUNK_SIZE):
        chunk_records = records[chunk_num:chunk_num + CHUNK_SIZE]
        chunk_file = os.path.join(CHUNK_DIR, f"chunk_{chunk_num // CHUNK_SIZE:04d}.bin")
        with open(chunk_file, "wb") as f:
            for r in chunk_records:
                offset = f.tell()
                f.write(r["data"])
                index[r["id"]] = {
                    "chunk": chunk_num // CHUNK_SIZE,
                    "offset": offset,
                    "size": r["size"],
                }
    with open(CHUNK_INDEX_PATH, "w") as f:
        json.dump(index, f)
    return index


def load_chunked_index():
    with open(CHUNK_INDEX_PATH, "r") as f:
        raw = json.load(f)
    return {int(k): v for k, v in raw.items()}


def read_record_chunked(index, record_id):
    """Read a single record from the appropriate chunk file."""
    entry = index[record_id]
    chunk_file = os.path.join(CHUNK_DIR, f"chunk_{entry['chunk']:04d}.bin")
    with open(chunk_file, "rb") as f:
        f.seek(entry["offset"])
        return f.read(entry["size"])



# Strategy C - Individual Files

INDIVIDUAL_DIR = "results/strategy_c_individual"


def write_individual_files(records):
    """Write each record to its own file."""
    if os.path.exists(INDIVIDUAL_DIR):
        shutil.rmtree(INDIVIDUAL_DIR)
    os.makedirs(INDIVIDUAL_DIR, exist_ok=True)

    for r in records:
        path = os.path.join(INDIVIDUAL_DIR, f"record_{r['id']:08d}.bin")
        with open(path, "wb") as f:
            f.write(r["data"])


def read_record_individual(record_id):
    """Read a single record by constructing its filename."""
    path = os.path.join(INDIVIDUAL_DIR, f"record_{record_id:08d}.bin")
    with open(path, "rb") as f:
        return f.read()
