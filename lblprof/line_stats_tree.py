import logging
import os
from typing import List, Dict, Tuple, Optional
from lblprof.curses_ui import TerminalTreeUI
from lblprof.line_stat_object import LineStats, LineKey, LineEvent


def make_key(event: LineEvent) -> Tuple[LineKey, Tuple[LineKey, ...]]:
    return (
        LineKey(
            file_name=event["file_name"],
            function_name=event["function_name"],
            line_no=event["line_no"],
        ),
        tuple(
            LineKey(
                file_name=key[0],
                function_name=key[1],
                line_no=key[2],
            )
            for key in event["stack_trace"]
        ),
    )


class LineStatsTree:
    """A tree structure to manage LineStats objects with automatic parent-child time propagation."""

    def __init__(self):
        self.raw_events_list: List[LineEvent] = []
        self.events_index: Dict[Tuple[LineKey, Tuple[LineKey, ...]], LineStats] = {}
        # Store all lines by their key
        self.lines: Dict[Tuple[LineKey], LineStats] = {}
        # Track root nodes (entry points with no parents)
        self.root_lines: List[LineStats] = []
        # Total time for all tracked lines
        self.total_time_ms: float = 0
        # cache of source code for lines
        # key is (file_name, line_no) for a source code line
        self.line_source: Dict[Tuple[str, int], str] = {}

    def add_line_event(
        self,
        file_name: str,
        function_name: str,
        line_no: int,
        start_time: float,
        stack_trace: List[Tuple[str, str, int]],
    ) -> None:
        """Add a line event to the tree."""
        if "stop_tracing" in function_name:
            return

        logging.debug(
            f"Adding line event: {file_name}::{function_name}::{line_no} at {start_time}::{stack_trace}"
        )
        self.raw_events_list.append(
            {
                "file_name": file_name,
                "function_name": function_name,
                "line_no": line_no,
                "start_time": start_time,
                "stack_trace": stack_trace,
            }
        )

    def build_tree(self) -> None:
        """Build the tree from the raw events list."""
        for i, event in enumerate(self.raw_events_list):
            source = self._get_source_code(event["file_name"], event["line_no"])
            if "stop_tracing" in source:
                # This allow to delete the line from the tree
                # and set the end line for the root lines
                event["line_no"] = 9999999
            event_key = make_key(event)
            self.events_index[event_key] = LineStats(
                file_name=event["file_name"],
                function_name=event["function_name"],
                line_no=event["line_no"],
                stack_trace=event["stack_trace"],
                start_time=event["start_time"],
                hits=1,
                avg_time=0.0,
                source=source,
            )
        for event in self.raw_events_list:
            # establish parent-child relationships
            event_key = make_key(event)
            node = self.events_index[event_key]

            # Get parent from stack trace
            if len(event["stack_trace"]) == 0:
                # we are in a root line
                self.root_lines.append(self.events_index[event_key])
                continue

            parent_stack, parent_key = event_key[1][:-1], event_key[1][-1]
            parent_stack = tuple(
                LineKey(
                    file_name=key.file_name,
                    function_name=key.function_name,
                    line_no=key.line_no,
                )
                for key in parent_stack
            )

            if parent_key:
                parent_node = self.events_index.get((parent_key, parent_stack))
                if parent_node:
                    node.parent = (parent_key, parent_stack)
                    parent_node.childs.append(node)

        # update time line by line
        for current_line in self.events_index.values():
            if current_line.line_no > 999999:
                continue
            brothers = (
                self.root_lines
                if current_line.parent is None
                else self.events_index[current_line.parent].childs
            )

            def _get_next_brother(
                line: LineStats, brothers: List[LineStats]
            ) -> LineStats:
                """Get the next brother of the current line."""
                current_line_nb = line.line_no
                brothers_line_nb = [brother.line_no for brother in brothers]
                brothers_line_nb.sort()
                for brother_line_nb in brothers_line_nb:
                    if brother_line_nb > current_line_nb:
                        return brothers[brothers_line_nb.index(brother_line_nb)]
                logging.warning(f"Line info: {current_line}")
                logging.warning(f"Brothers info: {brothers}")
                raise ValueError(
                    f"No next brother found for line {current_line.line_no}"
                )

            next_brother = _get_next_brother(current_line, brothers)
            current_line.time = next_brother.start_time - current_line.start_time

        # delete all lines with line_no > 999999
        self.root_lines = [line for line in self.root_lines if line.line_no <= 999999]
        self.events_index = {
            key: line
            for key, line in self.events_index.items()
            if line.line_no <= 999999
        }

    def _get_source_code(self, file_name: str, line_no: int) -> str:
        """Get the source code for a specific line in a file."""
        if (file_name, line_no) in self.line_source:
            return self.line_source[(file_name, line_no)]
        try:
            with open(file_name, "r") as f:
                lines = f.readlines()
                if line_no - 1 < len(lines):
                    source = lines[line_no - 1].strip()
                    self.line_source[(file_name, line_no)] = source
                    return source
                else:
                    return " "
        except Exception as e:
            return (
                f"Error getting source code of line {line_no} in file {file_name}: {e}"
            )

    def display_tree(
        self,
        root_key: Optional[Tuple[LineKey, Tuple[LineKey, ...]]] = None,
        depth: int = 0,
        max_depth: int = 10,
        is_last: bool = True,
        prefix: str = "",
    ) -> None:
        """Display a visual tree showing parent-child relationships between lines.

        Args:
            root_key: Optional[Tuple[LineKey, Tuple[LineKey, ...]]] - If provided, start from this line.
                                                    If None, start from all root lines.
            depth: int - Current recursion depth (for internal use).
            max_depth: int - Maximum depth to display.
            is_last: bool - Whether this node is the last child of its parent (for drawing)
            prefix: str - The prefix string for the current line (for drawing)
        """
        if depth > max_depth:
            return  # Prevent infinite recursion

        # Tree branch characters
        branch_mid = "├── "
        branch_last = "└── "
        pipe = "│   "
        space = "    "

        def format_line_info(line: LineStats, branch: str):
            filename = os.path.basename(line.file_name)
            line_id = f"{filename}::{line.function_name}::{line.line_no}"

            # Truncate source code
            truncated_source = (
                line.source[:60] + "..." if len(line.source) > 60 else line.source
            )

            # Display line with time info and hits count
            assert line.time is not None
            return f"{prefix}{branch}{line_id} [hits:{line.hits} total:{line.time*1000:.2f}ms] - {truncated_source}"

        def group_children_by_file(children):
            children_by_file = {}
            for child in children:
                if child.file_name not in children_by_file:
                    children_by_file[child.file_name] = []
                children_by_file[child.file_name].append(child)

            # Sort each file's lines by line number
            for file_name in children_by_file:
                children_by_file[file_name].sort(key=lambda x: x.line_no)

            return children_by_file

        def get_all_children(children_by_file):
            all_children = []
            for file_name in children_by_file:
                all_children.extend(children_by_file[file_name])
            return all_children

        if root_key:
            if root_key not in self.events_index:
                return

            line = self.events_index[root_key]
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
                self.display_tree(
                    child.event_key, depth + 1, max_depth, is_last_child, next_prefix
                )
        else:
            # Print all root trees
            root_lines = self.root_lines
            if not root_lines:
                print("No root lines found in stats")
                return

            print("\n\nLINE TRACE TREE (HITS / SELF TIME / TOTAL TIME):")
            print("=================================================")

            # Sort roots by total time (descending)
            root_lines.sort(
                key=lambda x: x.time if x.time is not None else 0, reverse=True
            )

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
                    self.display_tree(
                        child.event_key, 1, max_depth, is_last_child, next_prefix
                    )

                # Add empty line between roots
                if not is_last_root:
                    print()

    def show_interactive(self, min_time_ms: int = 1):
        """Display the tree in an interactive terminal interface."""

        # Define the data provider
        # Given a node (a line), return its children
        def get_tree_data(node_key=None):
            if node_key is None:
                # Return root nodes
                return [
                    line for line in self.root_lines if line.total_time >= min_time_ms
                ]
            else:
                # Return children of the specified node
                return [
                    self.lines[child_key]
                    for child_key in self.lines[node_key].child_keys
                    if child_key in self.lines
                    and self.lines[child_key].total_time >= min_time_ms
                ]

        # Define the node formatter function
        # Given a line, return its formatted string (displayed in the UI)
        def format_node(line, indicator=""):
            filename = os.path.basename(line.file_name)
            line_id = f"{filename}::{line.function_name}::{line.line_no}"

            # Truncate source code
            truncated_source = (
                line.source[:40] + "..." if len(line.source) > 40 else line.source
            )

            # Format stats
            stats = f"[hits:{line.hits} self:{line.self_time:.2f}ms total:{line.total_time:.2f}ms]"

            # Return formatted line
            return f"{indicator}{line_id} {stats} - {truncated_source}"

        # Create and run the UI
        ui = TerminalTreeUI(get_tree_data, format_node)
        ui.run()
