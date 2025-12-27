import inspect
import sys

from lblprof.display_tree import show_interactive
from lblprof.line_stats_tree import LineStatsTree
from lblprof.print_tree import print_tree
from lblprof.runtime_monitoring import (
    InstrumentationFinder,
    clear_cache_modules,
)
from lblprof.sys_monitoring import CodeMonitor, instrument_code_recursive

# Create a singleton instance for the module
tracer = CodeMonitor()

# Import the sys.monitoring-based tracer if Python 3.12+ is available
if not hasattr(sys, "monitoring"):
    msg = "Python 3.12+ is required to use lblprof"
    raise RuntimeError(msg)


def start_monitoring() -> None:
    # TODO put most of this code away in a function that takes the
    # tracer and the caller frame

    # 1. Register sys.monitoring hooks
    tracer.reset_monitoring()
    tracer.register_hooks()

    # 2. Find the *current* module (the one calling start_monitoring)
    caller_frame = inspect.stack()[1]
    caller_code = caller_frame.frame.f_code
    instrument_code_recursive(caller_code)

    # 3. Install import hook to instrument future imports
    sys.meta_path.insert(0, InstrumentationFinder())

    # 4. Remove already loaded modules that match the filter dirs so they can be
    clear_cache_modules()


def stop_monitoring() -> None:
    """Stop tracing code execution."""
    tracer.stop_monitoring()

    # remove the custom finder
    if isinstance(sys.meta_path[0], InstrumentationFinder):
        sys.meta_path = sys.meta_path[1:]


def show_tree() -> None:
    """Display the tree structure."""
    tree = LineStatsTree(tracer.events)
    tree.build_tree()
    print_tree(tree)


# Add a module-level function to expose the interactive UI
def show_interactive_tree(min_time_s: float = 0) -> None:
    """Display an interactive tree in the terminal."""
    tree = LineStatsTree(tracer.events)
    tree.build_tree()
    show_interactive(tree.root_lines, min_time_s=min_time_s)
