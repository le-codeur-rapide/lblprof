from .custom_tracer import CodeTracer

# Create a singleton instance for the module
tracer = CodeTracer()


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
