# ruff: noqa: T201

from pathlib import Path

from lblprof.line_stat_object import LineStats


def print_tree(
    events_index: dict[int, LineStats],
    root_lines: list[LineStats],
    root_key: int | None = None,
    depth: int = 0,
    max_depth: int = 10,
    is_last: bool = True,
    prefix: str = "",
) -> None:
    """Display a visual tree showing parent-child relationships between lines."""
    if depth > max_depth:
        return  # Prevent infinite recursion

    # Tree branch characters
    branch_mid = "├── "
    branch_last = "└── "
    pipe = "│   "
    space = "    "

    def format_line_info(line: LineStats, branch: str) -> str:
        filename = Path(line.file_name).name
        line_id = f"{filename}::{line.func_name}::{line.line_no}"

        # Truncate source code
        truncated_source = (
            line.source[:60] + "..." if len(line.source) > 60 else line.source
        )

        # Display line with time info and hits count
        return (
            f"{prefix}{branch}{line_id} [hits:{line.hits} "
            f"total:{line.duration * 1000:.2f}ms] - {truncated_source}"
        )

    def group_children_by_file(
        children: dict[int, LineStats],
    ) -> dict[str, list[LineStats]]:
        children_by_file: dict[str, list[LineStats]] = {}
        for child in children.values():
            if child.file_name not in children_by_file:
                children_by_file[child.file_name] = []
            children_by_file[child.file_name].append(child)

        # Sort each file's lines by line number
        for file_name in children_by_file:
            children_by_file[file_name].sort(key=lambda x: x.line_no)

        return children_by_file

    def get_all_children(
        children_by_file: dict[str, list[LineStats]],
    ) -> list[LineStats]:
        all_children: list[LineStats] = []
        for file_name in children_by_file:
            all_children.extend(children_by_file[file_name])
        return all_children

    if root_key:
        line = events_index[root_key]
        branch = branch_last if is_last else branch_mid
        print(format_line_info(line, branch))

        # Get all child lines
        child_lines = line.childs

        # Group and organize children
        children_by_file = group_children_by_file(child_lines)
        all_children = get_all_children(children_by_file)

        # Display child lines in order
        next_prefix = prefix + (space if is_last else pipe)
        for i, child in enumerate(all_children):
            is_last_child = i == len(all_children) - 1
            print_tree(
                events_index,
                root_lines,
                child.id,
                depth + 1,
                max_depth,
                is_last_child,
                next_prefix,
            )
    else:
        # Print all root trees
        root_lines = root_lines
        if not root_lines:
            print("No root lines found in stats")
            return

        print("\n\nLINE TRACE TREE (HITS / SELF TIME / TOTAL TIME):")
        print("=================================================")

        # Sort roots by total time (descending)
        root_lines.sort(key=lambda x: x.line_no if x.line_no else 0, reverse=False)

        # For each root, render as a separate tree
        for i, root in enumerate(root_lines):
            is_last_root = i == len(root_lines) - 1
            branch = branch_last if is_last_root else branch_mid

            print(format_line_info(root, branch))

            # Get all child lines and organize them
            children_by_file = group_children_by_file(root.childs)
            all_children = get_all_children(children_by_file)

            # Display child lines in order
            next_prefix = space if is_last_root else pipe
            for j, child in enumerate(all_children):
                is_last_child = j == len(all_children) - 1
                print_tree(
                    events_index,
                    root_lines,
                    child.id,
                    1,
                    max_depth,
                    is_last_child,
                    next_prefix,
                )
