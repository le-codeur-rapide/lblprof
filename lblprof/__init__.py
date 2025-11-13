import sys

# Import the base tracer that works on all Python versions
from .sys_monitoring import CodeMonitor
from .runtime_monitoring import start_profiling_

# Create a singleton instance for the module
tracer = CodeMonitor()

# Import the sys.monitoring-based tracer if Python 3.12+ is available
if not hasattr(sys, "monitoring"):
    raise RuntimeError("Python 3.12+ is required to use lblprof")


def start_profiling() -> None:
    """Start tracing code execution."""
    start_profiling_(tracer)


def stop_profiling() -> None:
    """Stop tracing code execution."""
    tracer.stop_monitoring()
    tracer.build_tree()


def show_tree() -> None:
    """Display the tree structure."""
    tracer.tree.display_tree()


# Add a module-level function to expose the interactive UI
def show_interactive_tree(min_time_s: float = 0):
    """Display an interactive tree in the terminal."""
    tracer.tree.show_interactive(min_time_s=min_time_s)
