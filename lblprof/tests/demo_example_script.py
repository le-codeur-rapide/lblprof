import os
import logging
import sys
import time
import runpy

sys.path.append(os.getcwd())
from lblprof import show_interactive_tree, start_monitoring, stop_profiling, tracer

logging.basicConfig(level=logging.DEBUG)


path_example_folder = os.path.join(os.path.dirname(__file__), "example_scripts")
script_name = "data_computation.py"
# script_name = "chroma_vector_search.py"
# script_name = "fibonacci.py"
script_name = "import_pandas.py"
# script_name = "list_comprehension.py"
# script_name = "try_except.py"
script_name = "double_zip.py"
# script_name = "generator_function.py"
script_path = os.path.join(path_example_folder, script_name)


def main2():
    time.sleep(1)


def main():
    time.sleep(1)
    main2()
    return


# reset cache
# start_time = time.perf_counter()
# subprocess.run(["python", script_path])
# end_time = time.perf_counter()
# print(f"Time taken: {end_time - start_time} seconds")


# run the tracer for a bit and return the tree
start_monitoring()
# time.sleep(1)
# main()
# import pandas as pd  # noqa: E402,F401

# Load and execute the example script
start_time = time.perf_counter()
runpy.run_path(script_path, run_name="__main__")
end_time = time.perf_counter()
print(f"Time taken: {end_time - start_time} seconds")

stop_profiling()
# print the tree
# show_tree()
show_interactive_tree(min_time_s=0.0)
tracer.tree._save_events()
tracer.tree._save_events_index()
