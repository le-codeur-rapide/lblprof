import logging
import sys

# Import the base tracer that works on all Python versions
from .custom_sysmon import CodeMonitor


__all__ = ["CodeMonitor"]
# Create a singleton instance for the module
tracer = CodeMonitor()

# Import the sys.monitoring-based tracer if Python 3.12+ is available
if hasattr(sys, "monitoring"):
    from .custom_sysmon import CodeMonitor

    __all__.append("CodeMonitor")
    tracer = CodeMonitor()
else:
    logging.warning("Python 3.12+ is required to use the sys.monitoring-based tracer.")


def set_custom_trace() -> None:
    """Start tracing code execution."""
    tracer.start_tracing()


def stop_custom_trace() -> None:
    """Stop tracing code execution."""
    tracer.stop_tracing()


def show_tree() -> None:
    """Display the tree structure."""
    tracer.tree.display_tree()


# Add a module-level function to expose the interactive UI
def show_interactive_tree(min_time_ms: int = 1):
    """Display an interactive tree in the terminal."""
    tracer.tree.show_interactive(min_time_ms=min_time_ms)
