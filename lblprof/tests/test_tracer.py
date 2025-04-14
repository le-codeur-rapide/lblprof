import os
import pytest
from unittest.mock import patch, MagicMock
from lblprof.tracer import CodeTracer
from lblprof.line_stats_tree import LineStatsTree


@pytest.fixture
def tracer():
    """Fixture to create a CodeTracer instance for each test."""
    tracer = CodeTracer()
    yield tracer
    tracer.stop_tracing()


def test_init(tracer):
    """Test initialization of CodeTracer."""
    assert isinstance(tracer.line_source, dict)
    assert isinstance(tracer.call_stack, list)
    assert isinstance(tracer.tree, LineStatsTree)
    assert tracer.tempo_line_infos is None
    assert isinstance(tracer.site_packages_paths, list)


def test_is_installed_module(tracer):
    """Test detection of installed modules."""
    # Should return True for installed modules
    assert tracer._is_installed_module(
        "/usr/lib/python3.8/site-packages/numpy/__init__.py"
    )
    assert tracer._is_installed_module(
        "/usr/local/lib/python3.8/site-packages/pandas/__init__.py"
    )
    assert tracer._is_installed_module("frozen importlib")
    assert tracer._is_installed_module("frozen zipimport")
    assert tracer._is_installed_module("<built-in>")

    # Should return False for user modules
    assert not tracer._is_installed_module("/home/user/my_project/main.py")
    assert not tracer._is_installed_module("example_script.py")


@patch("sys.settrace")
def test_start_tracing(mock_settrace, tracer):
    """Test starting the tracer."""
    tracer.start_tracing()
    mock_settrace.assert_called_once_with(tracer.trace_function)


@patch("sys.settrace")
def test_stop_tracing(mock_settrace, tracer):
    """Test stopping the tracer."""
    tracer.stop_tracing()
    mock_settrace.assert_called_once_with(None)


def test_trace_function_call_event(tracer):
    """Test handling of 'call' event in trace_function."""
    # Create mock frame objects
    mock_frame = MagicMock()
    mock_frame.f_code.co_name = "test_function"
    mock_frame.f_code.co_filename = "test_file.py"
    mock_frame.f_lineno = 10
    mock_frame.f_back.f_code.co_name = "caller_function"
    mock_frame.f_back.f_code.co_filename = "caller_file.py"
    mock_frame.f_back.f_lineno = 20

    # Call the trace function with 'call' event
    result = tracer.trace_function(mock_frame, "call", None)

    # Check that the call stack was updated
    assert len(tracer.call_stack) == 1
    assert tracer.call_stack[0] == ("caller_file.py", "caller_function", 20)

    # Check that the function returns itself to continue tracing
    assert result == tracer.trace_function


def test_trace_function_line_event(tracer):
    """Test handling of 'line' event in trace_function."""
    # Create a temporary file for testing
    with open("temp_test_file.py", "w") as f:
        f.write("def test_function():\n    print('Hello')\n")

    # Create mock frame objects
    mock_frame = MagicMock()
    mock_frame.f_code.co_name = "test_function"
    mock_frame.f_code.co_filename = "temp_test_file.py"
    mock_frame.f_lineno = 2

    # Set up call stack
    tracer.call_stack = [("caller_file.py", "caller_function", 20)]

    # Call the trace function with 'line' event
    result = tracer.trace_function(mock_frame, "line", None)

    # Check that the function returns itself to continue tracing
    assert result == tracer.trace_function

    # Clean up
    os.remove("temp_test_file.py")


def test_trace_function_return_event(tracer):
    """Test handling of 'return' event in trace_function."""
    # Create mock frame objects
    mock_frame = MagicMock()
    mock_frame.f_code.co_name = "test_function"
    mock_frame.f_code.co_filename = "test_file.py"
    mock_frame.f_lineno = 10

    # Set up call stack
    tracer.call_stack = [("caller_file.py", "caller_function", 20)]

    # Call the trace function with 'return' event
    result = tracer.trace_function(mock_frame, "return", None)

    # Check that the call stack was updated
    assert len(tracer.call_stack) == 0

    # Check that the function returns itself to continue tracing
    assert result == tracer.trace_function


def test_trace_actual_code_execution(tracer):
    """Test tracing actual code execution."""
    # Create a temporary test module
    test_module_path = os.path.abspath("test_module.py")
    with open(test_module_path, "w") as f:
        f.write(
            """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def main():
    result = fibonacci(5)
    print(f"Fibonacci(5) = {result}")
    
if __name__ == "__main__":
    main()
"""
        )

    # Start tracing
    tracer.start_tracing()

    # Import and run the test module
    import importlib.util

    spec = importlib.util.spec_from_file_location("test_module", test_module_path)
    if spec is not None and spec.loader is not None:
        test_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(test_module)

    # Stop tracing
    tracer.stop_tracing()

    # Clean up
    os.remove(test_module_path)

    # Verify that the tracer captured the execution
    # Check that we have line stats in the tree
    assert len(tracer.tree.lines) > 0

    # Check that we captured the fibonacci function
    fibonacci_lines = [
        line for line in tracer.tree.lines.values() if line.function_name == "fibonacci"
    ]
    assert len(fibonacci_lines) > 0

    # Check that we captured the main function
    main_lines = [
        line for line in tracer.tree.lines.values() if line.function_name == "main"
    ]
    assert len(main_lines) > 0

    # Check that the call stack is empty after execution
    assert len(tracer.call_stack) == 0
