import runpy
import os
import logging
import sys

sys.path.append(os.getcwd())
from lblprof import set_custom_trace, stop_custom_trace, show_interactive_tree

logging.basicConfig(level=logging.DEBUG)


path_example_folder = os.path.join(os.path.dirname(__file__), "example_scripts")
script_name = "data_computation.py"
script_path = os.path.join(path_example_folder, script_name)

# run the tracer for a bit and return the tree
set_custom_trace()

# Load and execute the example script
runpy.run_path(script_path, run_name="__main__")

stop_custom_trace()
# print the tree
print(show_interactive_tree())
