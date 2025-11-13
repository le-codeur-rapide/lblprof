import pytest
from lblprof.line_stats_tree import LineStatsTree


@pytest.fixture
def tree():
    """Fixture to create a LineStatsTree instance for each test."""
    return LineStatsTree([])


# def test_add_line_event(tree: LineStatsTree):
#     """Test adding a line event to the tree."""
#     # Create a line with no parent (root line)
#     tree.add_line_event(
#         id=1,
#         file_name="test_file.py",
#         function_name="test_function",
#         line_no=10,
#         start_time=0.0,
#         stack_trace=[("test_file.py", "test_function", 10)],
#     )

#     assert len(tree.raw_events_list) == 1
#     assert tree.raw_events_list[0]["id"] == 1
#     assert tree.raw_events_list[0]["file_name"] == "test_file.py"
#     assert tree.raw_events_list[0]["function_name"] == "test_function"
#     assert tree.raw_events_list[0]["line_no"] == 10
#     assert tree.raw_events_list[0]["start_time"] == 0.0
#     assert tree.raw_events_list[0]["stack_trace"] == [
#         ("test_file.py", "test_function", 10)
#     ]


# def test_add_line_event_with_parent(tree: LineStatsTree):
#     """Test adding a line event with a parent in the tree."""
#     # Create a parent line
#     tree.add_line_event(
#         id=1,
#         file_name="test_file.py",
#         function_name="parent_function",
#         line_no=5,
#         start_time=0.0,
#         stack_trace=[("test_file.py", "parent_function", 5)],
#     )

#     # Create a child line
#     tree.add_line_event(
#         id=2,
#         file_name="test_file.py",
#         function_name="child_function",
#         line_no=10,
#         start_time=0.0,
#         stack_trace=[("test_file.py", "child_function", 10)],
#     )

#     # Check that both lines were added to the tree
#     assert len(tree.raw_events_list) == 2


# def test_get_source_code(tree: LineStatsTree):
#     """Test getting source code for a line."""
#     # Create a temporary file
#     with open("temp_test_file.py", "w") as f:
#         f.write("def test_function():\n    print('Hello')\n")

#     # Get source code
#     source = tree._get_source_code("temp_test_file.py", 2)

#     # Check that the source code is correct
#     assert source == "print('Hello')"

#     # Clean up
#     os.remove("temp_test_file.py")
