import importlib
import logging
from pathlib import Path

import pytest

from lblprof import show_tree, start_monitoring, stop_monitoring, tracer
from lblprof.line_stats_tree import LineStatsTree

logging.basicConfig(level=logging.DEBUG)


# It is hard to get reliable tests for some example of code, something that we
# can do is to check that the tree is coherent
#   - A line should have a parent key if and only if it is a child of another line
#   - The sum of the time of the children should be equal to the time of the parent
#   - Whatever the line, if it is time.sleep(n), then the time should be n

# Get all Python files from the example_scripts directory
EXAMPLE_SCRIPTS_DIR = Path(__file__).parent / "example_scripts"
EXAMPLE_SCRIPTS = [
    f.name.replace(".py", "")
    for f in EXAMPLE_SCRIPTS_DIR.iterdir()
    if f.is_file() and f.name.endswith(".py") and not f.name.startswith("__")
]


@pytest.fixture(params=EXAMPLE_SCRIPTS, ids=lambda x: x)
def tree(request: pytest.FixtureRequest) -> LineStatsTree:
    start_monitoring()
    importlib.import_module(f"example_scripts.{request.param}")
    stop_monitoring()
    # print the tree
    show_tree()
    return tracer.tree


def test_tree_coherence(tree: LineStatsTree):
    validate_parent_child_relations(tree)
    validate_time_sleep(tree)


def validate_parent_child_relations(tree: LineStatsTree):
    for line in tree.events_index.values():
        if line.parent is None:
            continue
        assert line.parent in tree.events_index, (
            f"Parent key {line.parent} not found in tree: line {line}"
        )
        assert line.id in [
            child.id for child in tree.events_index[line.parent].childs.values()
        ], f"Line {line.id} should have parent key {line.parent}"


def validate_time_sleep(tree: LineStatsTree):
    """Assert that the time.sleep lines have the correct time"""
    for line in tree.root_lines:
        if "time.sleep" in line.source:
            n = line.source.split("time.sleep(")[1].split(")")[0]
            total_time = float(n) * line.hits * 1000
            assert line.duration == pytest.approx(total_time, rel=0.1), (
                f"Line {line.id} should have time "
                f"{total_time} but has time {line.duration}"
            )


def validate_parent_time_is_sum_of_children_time(tree: LineStatsTree):
    for line in tree.events_index.values():
        if not line.childs:
            return
        sum_child_durations = sum(
            [child.duration for child in line.childs.values()],
        )
        assert line.duration == sum_child_durations, (
            f"Line {line.id} should have time "
            f"{sum_child_durations} but has time {line.duration}"
        )
