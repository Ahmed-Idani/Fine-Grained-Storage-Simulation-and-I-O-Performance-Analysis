import shutil
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from benchmarks import run_benchmarks


def clean_results():
    for name in [
        "results/strategy_a.bin",
        "results/strategy_a_index.json",
        "results/strategy_b_chunks",
        "results/strategy_b_index.json",
        "results/strategy_c_individual",
        "results/benchmark_results.csv",
    ]:
        path = os.path.join(BASE_DIR, name)
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.isfile(path):
            os.remove(path)


if __name__ == "__main__":
    print("Cleaning previous results...")
    clean_results()
    print()
    run_benchmarks()
    print("\nDone! See results/benchmark_results.csv and report.md")
