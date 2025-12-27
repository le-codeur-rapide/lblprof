# ruff: noqa: T201

from pathlib import Path

from lblprof.line_stat_object import LineStats
from lblprof.line_stats_tree import LineStatsTree
from lblprof.utils.event_index_utils import get_sorted_children
from lblprof.utils.source_code_utils import truncate_line
from lblprof.utils.visual_constants import (
    BRANCH_LAST_CHARS,
    BRANCH_MID_CHARS,
    PIPE_CHARS,
    SPACE_CHARS,
)

TREE_MAX_DEPTH = 10
MAX_SOURCE_LENGTH = 60


def format_line_info(line: LineStats, branch: str, prefix: str) -> str:
    filename = Path(line.file_name).name
    line_id = f"{filename}::{line.func_name}::{line.line_no}"
    truncated_source = truncate_line(line.source, MAX_SOURCE_LENGTH)
    return (
        f"{prefix}{branch}{line_id} [hits:{line.hits} "
        f"total:{line.duration * 1000:.2f}ms] - {truncated_source}"
    )


def print_tree(
    line_stats_tree: LineStatsTree,
) -> None:
    root_lines = line_stats_tree.root_lines
    events_index = line_stats_tree.events_index
    print("\n\nLINE TRACE TREE (HITS / SELF TIME / TOTAL TIME):")
    print("=================================================")

    # Sort roots by total time (descending)
    root_lines.sort(key=lambda x: x.line_no if x.line_no else 0, reverse=False)

    # For each root, render as a separate tree
    for i, root in enumerate(root_lines):
        is_last_root = i == len(root_lines) - 1
        branch = BRANCH_LAST_CHARS if is_last_root else BRANCH_MID_CHARS

        print(format_line_info(root, branch, ""))

        # Get all child lines and organize them
        all_children = get_sorted_children(list(root.childs.values()))

        # Display child lines in order
        next_prefix = SPACE_CHARS if is_last_root else PIPE_CHARS
        for j, child in enumerate(all_children):
            is_last_child = j == len(all_children) - 1
            print_line_recursively(
                events_index,
                child.id,
                1,
                is_last_child,
                next_prefix,
            )


def print_line_recursively(
    events_index: dict[int, LineStats],
    root_key: int,
    depth: int = 0,
    is_last: bool = True,
    prefix: str = "",
) -> None:
    """Display a visual tree showing parent-child relationships between lines."""
    if depth > TREE_MAX_DEPTH:
        return  # Prevent infinite recursion

    line = events_index[root_key]
    branch = BRANCH_LAST_CHARS if is_last else BRANCH_MID_CHARS
    print(format_line_info(line, branch, prefix))

    # Get all child lines
    child_lines = line.childs

    # Group and organize children
    all_children = get_sorted_children(list(child_lines.values()))

    # Display child lines in order
    next_prefix = prefix + (SPACE_CHARS if is_last else PIPE_CHARS)
    for i, child in enumerate(all_children):
        is_last_child = i == len(all_children) - 1
        print_line_recursively(
            events_index,
            child.id,
            depth + 1,
            is_last_child,
            next_prefix,
        )
