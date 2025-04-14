import os
import pytest
from lblprof.line_stats_tree import LineStatsTree


@pytest.fixture
def tree():
    """Fixture to create a LineStatsTree instance for each test."""
    return LineStatsTree()


def test_create_line(tree: LineStatsTree):
    """Test creating a line in the tree."""
    # Create a line with no parent (root line)
    tree.create_line(
        file_name="test_file.py",
        function_name="test_function",
        line_no=10,
        hits=1,
        time_ms=5.0,
        source="print('Hello')",
    )

    # Check that the line was added to the tree
    assert len(tree.lines) == 1
    assert len(tree.root_lines) == 1

    # Get the line
    line_key = ("test_file.py", "test_function", 10)
    line = tree.lines[line_key]

    # Check line properties
    assert line.file_name == "test_file.py"
    assert line.function_name == "test_function"
    assert line.line_no == 10
    assert line.hits == 1
    assert line.time == 5.0
    assert line.avg_time == 5.0
    assert line.source == "print('Hello')"
    assert line.child_time == 0.0
    assert line.parent_key is None
    assert line.child_keys == []


def test_create_line_with_parent(tree: LineStatsTree):
    """Test creating a line with a parent in the tree."""
    # Create a parent line
    tree.create_line(
        file_name="test_file.py",
        function_name="parent_function",
        line_no=5,
        hits=1,
        time_ms=10.0,
        source="def parent_function():",
    )

    # Create a child line
    tree.create_line(
        file_name="test_file.py",
        function_name="child_function",
        line_no=10,
        hits=1,
        time_ms=5.0,
        source="print('Hello')",
        parent_key=("test_file.py", "parent_function", 5),
    )

    # Check that both lines were added to the tree
    assert len(tree.lines) == 2
    assert len(tree.root_lines) == 1

    # Get the lines
    parent_key = ("test_file.py", "parent_function", 5)
    child_key = ("test_file.py", "child_function", 10)
    parent = tree.lines[parent_key]
    child = tree.lines[child_key]

    # Check parent-child relationship
    assert parent.parent_key is None
    assert parent.child_keys == [child_key]
    assert child.parent_key == parent_key
    assert child.child_keys == []


def test_update_line_time(tree: LineStatsTree):
    """Test updating the time of a line."""
    # Create a line
    line_key = ("test_file.py", "test_function", 10)
    tree.create_line(
        file_name="test_file.py",
        function_name="test_function",
        line_no=10,
        hits=1,
        time_ms=5.0,
        source="print('Hello')",
    )

    # Update the line time
    tree.update_line_time(line_key, 10.0, 1)

    # Check that the line was updated
    line = tree.lines[line_key]
    assert line.time == 15.0  # 5.0 + 10.0
    assert line.hits == 2  # 1 + 1
    assert line.avg_time == 7.5  # 15.0 / 2


def test_update_parent_times(tree: LineStatsTree):
    """Test updating parent times when a child line is updated."""
    # Create a parent line
    parent_key = ("test_file.py", "parent_function", 5)
    tree.create_line(
        file_name="test_file.py",
        function_name="parent_function",
        line_no=5,
        hits=1,
        time_ms=10.0,
        source="def parent_function():",
    )

    # Create a child line
    child_key = ("test_file.py", "child_function", 10)
    tree.create_line(
        file_name="test_file.py",
        function_name="child_function",
        line_no=10,
        hits=1,
        time_ms=5.0,
        source="print('Hello')",
        parent_key=parent_key,
    )

    # Update the child line time
    tree.update_line_time(child_key, 10.0, 1)

    # Check that both lines were updated
    parent = tree.lines[parent_key]
    child = tree.lines[child_key]

    assert child.time == 15.0  # 5.0 + 10.0
    assert child.hits == 2  # 1 + 1
    assert child.avg_time == 7.5  # 15.0 / 2

    assert parent.time == 25.0  # 10.0 + 15
    assert parent.child_time == 15.0  # Child's time


def test_get_root_lines(tree: LineStatsTree):
    """Test getting root lines from the tree."""
    # Create a root line
    tree.create_line(
        file_name="test_file.py",
        function_name="root_function",
        line_no=5,
        hits=1,
        time_ms=10.0,
        source="def root_function():",
    )

    # Create a child line
    tree.create_line(
        file_name="test_file.py",
        function_name="child_function",
        line_no=10,
        hits=1,
        time_ms=5.0,
        source="print('Hello')",
        parent_key=("test_file.py", "root_function", 5),
    )

    # Get root lines
    root_lines = tree._get_root_lines()

    # Check that only the root line is returned
    assert len(root_lines) == 1
    assert root_lines[0].function_name == "root_function"


def test_get_source_code(tree: LineStatsTree):
    """Test getting source code for a line."""
    # Create a temporary file
    with open("temp_test_file.py", "w") as f:
        f.write("def test_function():\n    print('Hello')\n")

    # Get source code
    source = tree._get_source_code("temp_test_file.py", 2)

    # Check that the source code is correct
    assert source == "print('Hello')"

    # Clean up
    os.remove("temp_test_file.py")
