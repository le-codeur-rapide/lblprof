import runpy
import os
import pytest
import logging


from lblprof.line_stats_tree import LineStatsTree
from lblprof import show_tree, start_profiling, stop_profiling, tracer

logging.basicConfig(level=logging.DEBUG)


# It is hard to get reliable tests for some example of code, something that we
# can do is to check that the tree is coherent
#   - A line should have a parent key if and only if it is a child of another line
#   - The sum of the time of the children should be equal to the child time of the parent
#   - Whatever the line, if it is time.sleep(n), then the time should be n

# Get all Python files from the example_scripts directory
EXAMPLE_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "example_scripts")
EXAMPLE_SCRIPTS = [
    os.path.join(EXAMPLE_SCRIPTS_DIR, f)
    for f in os.listdir(EXAMPLE_SCRIPTS_DIR)
    if f.endswith(".py") and not f.startswith("__")
]


@pytest.fixture(params=EXAMPLE_SCRIPTS, ids=lambda x: os.path.basename(x))
def tree(request):
    # run the tracer for a bit and return the tree
    start_profiling()

    # Load and execute the example script
    runpy.run_path(request.param, run_name="__main__")

    stop_profiling()
    # print the tree
    print(f"Tree for {os.path.basename(request.param)}:")
    show_tree()
    return tracer.tree


def test_tree_coherence(tree: LineStatsTree):
    _validate_parent_child_relations(tree)
    _validate_time_sleep(tree)


def _validate_parent_child_relations(tree: LineStatsTree):
    for line in tree.events_index.values():
        if line.parent is None:
            continue
        assert (
            line.parent in tree.events_index
        ), f"Parent key {line.parent} not found in tree: line {line}"
        assert line.id in [
            child.id for child in tree.events_index[line.parent].childs.values()
        ], f"Line {line.id} should have parent key {line.parent}"


def _validate_time_sleep(tree: LineStatsTree):
    for line in tree.root_lines:
        if "time.sleep" in line.source:
            n = line.source.split("time.sleep(")[1].split(")")[0]
            total_time = float(n) * line.hits * 1000
            assert line.time == pytest.approx(
                total_time, rel=0.1
            ), f"Line {line.id} should have time {total_time} but has time {line.time}"
