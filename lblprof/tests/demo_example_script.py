import os
import logging
import sys
import time
import runpy

sys.path.append(os.getcwd())
from lblprof import (
    start_tracing,
    stop_tracing,
    show_tree,
    show_interactive_tree,
)

logging.basicConfig(level=logging.DEBUG)


path_example_folder = os.path.join(os.path.dirname(__file__), "example_scripts")
script_name = "data_computation.py"
# script_name = "chroma_vector_search.py"
# script_name = "fibonacci.py"
# script_name = "import_pandas.py"
script_path = os.path.join(path_example_folder, script_name)


def main2():
    time.sleep(1)


def main():
    time.sleep(1)
    main2()
    return


# run the tracer for a bit and return the tree
start_tracing()
# time.sleep(1)
# main()
# import pandas as pd  # noqa: E402,F401

# Load and execute the example script
runpy.run_path(script_path, run_name="__main__")

stop_tracing()
# print the tree
show_tree()
show_interactive_tree(min_time_s=0.0)
#
