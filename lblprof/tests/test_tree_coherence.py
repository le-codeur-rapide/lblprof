import runpy
import os
import pytest
import logging


from lblprof.line_stats_tree import LineStatsTree
from lblprof.custom_tracer import CodeTracer

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
    tracer = CodeTracer()
    tracer.start_tracing()

    # Load and execute the example script
    runpy.run_path(request.param, run_name="__main__")

    tracer.stop_tracing()
    # print the tree
    print(f"Tree for {os.path.basename(request.param)}:")
    print(tracer.tree.display_tree())
    return tracer.tree


def test_tree_coherence(tree: LineStatsTree):
    _validate_parent_child_relations(tree)
    _validate_children_time_sum(tree)
    _validate_time_sleep(tree)


def _validate_parent_child_relations(tree: LineStatsTree):
    for line in tree.lines.values():
        if line.parent_key is None:
            continue
        assert (
            line.parent_key in tree.lines
        ), f"Parent key {line.parent_key} not found in tree"
        assert (
            line.key in tree.lines[line.parent_key].child_keys
        ), f"Line {line.key} should have parent key {line.parent_key}"


def _validate_children_time_sum(tree: LineStatsTree):
    for line in tree.lines.values():
        if line.parent_key is None:
            continue
        sum_children_time = sum(
            tree.lines[child_key].time for child_key in line.child_keys
        )
        assert (
            line.child_time - sum_children_time < 1e-6
        ), f"Line {line.key} should have child time {line.child_time} but sum of children time {sum_children_time} is not equal"


def _validate_time_sleep(tree: LineStatsTree):
    for line in tree.lines.values():
        if "time.sleep" in line.source:
            n = line.source.split("time.sleep(")[1].split(")")[0]
            total_time = float(n) * line.hits * 1000
            assert line.time == pytest.approx(
                total_time, rel=0.1
            ), f"Line {line.key} should have time {total_time} but has time {line.time}"
