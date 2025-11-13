import inspect
import sys

# Import the base tracer that works on all Python versions
from .sys_monitoring import CodeMonitor, instrument_code_recursive
from .runtime_monitoring import (
    DEFAULT_FILTER_DIRS,
    InstrumentationFinder,
    clear_cache_modules,
)

# Create a singleton instance for the module
tracer = CodeMonitor()

# Import the sys.monitoring-based tracer if Python 3.12+ is available
if not hasattr(sys, "monitoring"):
    raise RuntimeError("Python 3.12+ is required to use lblprof")


def start_profiling():
    # 1. Register sys.monitoring hooks
    tracer.register_hooks()

    # 2. Find the *current* module (the one calling start_profiling)
    caller_frame = inspect.stack()[1]
    caller_code = caller_frame.frame.f_code
    instrument_code_recursive(caller_code)

    # 3. Install import hook to instrument future imports
    sys.meta_path.insert(0, InstrumentationFinder())

    # 4. Remove already loaded modules that match the filter dirs so they can be re-imported and instrumented
    clear_cache_modules([DEFAULT_FILTER_DIRS])


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
