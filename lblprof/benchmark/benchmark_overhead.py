import json
import logging
import subprocess
import sys
from typing import Literal

from lblprof.benchmark.funcs import sample_functions

logging.basicConfig(level=logging.INFO, force=True)


BenchRunMode = Literal["profiled", "unprofiled"]


def run(module: str, fn: str, mode: BenchRunMode) -> float:
    """Run the isolated benchmark process and return the time taken."""
    process_script_path = "lblprof/benchmark/bench_isolated_process.py"
    r = subprocess.check_output(
        [
            sys.executable,
            process_script_path,
            module,
            fn,
            mode,
        ],
    )
    return json.loads(r)["time"]


def print_bench_result(
    unprofiled_times: list[float],
    profiled_times: list[float],
) -> None:
    unprofiled_time = sum(unprofiled_times) / len(unprofiled_times)
    profiled_time = sum(profiled_times) / len(profiled_times)
    overhead = profiled_time - unprofiled_time
    overhead_pct = (
        (overhead / unprofiled_time) * 100 if unprofiled_time > 0 else float("inf")
    )
    logging.info(f"Unprofiled time: {unprofiled_time:.6f} s")
    logging.info(f"Profiled time:   {profiled_time:.6f} s")
    logging.info(f"Overhead:        {overhead:.6f} s ({overhead_pct:.2f}%)")


for func in sample_functions:
    module = func.__module__
    fn = func.__name__
    number_of_runs = 30
    profiled_times: list[float] = []
    unprofiled_times: list[float] = []
    for _ in range(number_of_runs):
        t_profiled = run(module, fn, "profiled")
        t_unprofiled = run(module, fn, "unprofiled")
        profiled_times.append(t_profiled)
        unprofiled_times.append(t_unprofiled)

    print_bench_result(unprofiled_times=unprofiled_times, profiled_times=profiled_times)
