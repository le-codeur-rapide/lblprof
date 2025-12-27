from pathlib import Path

from lblprof.curses_ui import TerminalTreeUI
from lblprof.line_stats_tree import LineStats

MAX_SOURCE_LENGTH = 40


def format_node(line: LineStats, indicator: str = "") -> str:
    """Format a line for display in the UI."""
    filename = Path(line.file_name).name
    line_id = f"{filename}::{line.func_name}::{line.line_no}"

    # Truncate source code
    truncated_source = (
        line.source[:MAX_SOURCE_LENGTH] + "..."
        if len(line.source) > MAX_SOURCE_LENGTH
        else line.source
    )

    # Format stats
    stats = f"[hits:{line.hits} time:{line.duration:.2f}s]"

    # Return formatted line
    return f"{indicator}{line_id} {stats} - {truncated_source}"


def show_interactive(root_lines: list[LineStats], min_time_s: float = 0.1) -> None:
    """Display the tree in an interactive terminal interface (curses)"""

    def get_tree_data(node_key: LineStats | None = None) -> list[LineStats]:
        """Return the children of the specified node.
        If node_key is None, return the root nodes.
        """
        if node_key is None:
            # Return root nodes
            return [
                line
                for line in root_lines
                if line.duration and line.duration >= min_time_s
            ]
        # Return children of the specified node
        return [
            child
            for child in node_key.id_childs_dict.values()
            if child.duration and child.duration >= min_time_s
        ]

    ui = TerminalTreeUI(get_tree_data, format_node)
    ui.run()
