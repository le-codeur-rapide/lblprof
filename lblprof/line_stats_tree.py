import logging
import os
from typing import List, Dict, Literal, Tuple, Optional, Union
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
        self.events_index: Dict[int, LineStats] = {}
        # Track root nodes (entry points with no parents)
        self.root_lines: List[LineStats] = []
        # Total time for all tracked lines
        self.total_time_ms: float = 0
        # cache of source code for lines
        # key is (file_name, line_no) for a source code line
        self.line_source: Dict[Tuple[str, int], str] = {}

    def add_line_event(
        self,
        id: int,
        file_name: str,
        function_name: str,
        line_no: Union[int, Literal["END_OF_FRAME"]],
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
                "id": id,
                "file_name": file_name,
                "function_name": function_name,
                "line_no": line_no,
                "start_time": start_time,
                "stack_trace": stack_trace,
            }
        )

    def save_events(self) -> None:
        """Save the events to a file."""
        with open("events.csv", "w") as f:
            for event in self.raw_events_list:
                f.write(
                    f"{event['id']},{event['file_name']},{event['function_name']},{event['line_no']},{event['start_time']}\n"
                )

    def save_events_index(self) -> None:
        """Save the events index to a file."""
        with open("events_index.csv", "w") as f:
            for key, event in self.events_index.items():
                f.write(
                    f"{event.id},{event.file_name.split('/')[-1]},{event.function_name},{event.line_no},{event.source},{event.hits},{event.start_time},{event.time},{len(event.childs)},{event.parent}\n"
                )

    def build_tree(self) -> None:
        """Build the tree from the raw events list."""
        self.save_events()
        for i, event in enumerate(self.raw_events_list):
            source = self._get_source_code(event["file_name"], event["line_no"])
            if "stop_tracing" in source:
                # This allow to delete the line from the tree
                # and set the end line for the root lines
                event["line_no"] = "END_OF_FRAME"
            event_key = event["id"]
            if event_key not in self.events_index:
                self.events_index[event_key] = LineStats(
                    id=event["id"],
                    file_name=event["file_name"],
                    function_name=event["function_name"],
                    line_no=event["line_no"],
                    stack_trace=event["stack_trace"],
                    start_time=event["start_time"],
                    hits=1,
                    avg_time=0.0,
                    source=source,
                )
            else:
                self.events_index[event_key].hits += 1

        for id, event in self.events_index.items():
            # establish parent-child relationships
            node = self.events_index[id]

            # Get parent from stack trace
            if len(event.stack_trace) == 0:
                # we are in a root line
                self.root_lines.append(self.events_index[id])
                continue

            # find id of parent_key in self.events_index
            parent_key = LineKey(
                file_name=event.stack_trace[-1][0],
                function_name=event.stack_trace[-1][1],
                line_no=event.stack_trace[-1][2],
            )
            parent_id = next(
                (
                    key
                    for key, line in self.events_index.items()
                    if line.event_key[0] == parent_key
                ),
                None,
            )
            if parent_id is None:
                logging.warning(
                    f"Parent key {event.stack_trace[-1]} not found in events index"
                )
                continue
            self.events_index[parent_id].childs.append(node)
            node.parent = parent_id
            self.events_index[id] = node

        # update time line by line
        # key is id of parent line
        # It is none for root lines
        time_save: Dict[Union[int, None], Tuple[int, float]] = {}
        for id, event in self.events_index.items():
            if event.parent not in time_save:
                logging.debug(
                    f"Saving time for parent {event.parent} with id {event.id} and start time {event.start_time}"
                )
                time_save[event.parent] = (event.id, event.start_time)
                continue
            logging.debug(
                f"Updating time for line {event.id} with parent {event.parent} and start time {event.start_time}"
            )
            previous_id, previous_start_time = time_save[event.parent]
            self.events_index[previous_id].time = event.start_time - previous_start_time
            time_save[event.parent] = (event.id, event.start_time)

        # remove END_OF_FRAME lines
        for id, event in list(self.events_index.items()):
            if event.line_no == "END_OF_FRAME":
                parent_id = event.parent
                if parent_id is not None:
                    self.events_index[parent_id].childs.remove(event)
                del self.events_index[id]

        self.root_lines = [
            line for line in self.events_index.values() if line.parent is None
        ]
        # merge lines that have same file_name, function_name and line_no
        grouped_events = {}

        def merge_events(event: LineStats):
            for child in event.childs:
                key = (child.file_name, child.function_name, child.line_no)
                if key not in grouped_events:
                    grouped_events[key] = child
                else:
                    grouped_events[key].time += child.time
                    grouped_events[key].hits += child.hits
                    grouped_events[key].childs.extend(child.childs)
                    merge_events(child)

        for event in self.root_lines:
            merge_events(event)

        # for id, event in self.events_index.items():
        #     key = (event.file_name, event.function_name, event.line_no)
        #     if key not in grouped_events:
        #         grouped_events[key] = event
        #     else:
        #         grouped_events[key].time += event.time
        #         grouped_events[key].hits += event.hits

        self.events_index = {}
        for key, event in grouped_events.items():
            self.events_index[event.id] = event

        self.save_events_index()

    def _get_source_code(
        self, file_name: str, line_no: Union[int, Literal["END_OF_FRAME"]]
    ) -> str:
        """Get the source code for a specific line in a file."""
        if line_no == "END_OF_FRAME":
            return "END_OF_FRAME"
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
        root_key: Optional[int] = None,
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

        def group_children_by_file(
            children: List[LineStats],
        ) -> Dict[str, List[LineStats]]:
            children_by_file = {}
            for child in children:
                if child.file_name not in children_by_file:
                    children_by_file[child.file_name] = []
                children_by_file[child.file_name].append(child)

            # Sort each file's lines by line number
            for file_name in children_by_file:
                children_by_file[file_name].sort(key=lambda x: x.line_no)

            return children_by_file

        def get_all_children(
            children_by_file: Dict[str, List[LineStats]]
        ) -> List[LineStats]:
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
                    child.id, depth + 1, max_depth, is_last_child, next_prefix
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
                key=lambda x: x.line_no if x.line_no is not None else 0, reverse=False
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
                        child.id, 1, max_depth, is_last_child, next_prefix
                    )

    def show_interactive(self, min_time_s: float = 0.1):
        """Display the tree in an interactive terminal interface."""

        # Define the data provider
        # Given a node (a line), return its children
        def get_tree_data(node_key: Optional[LineStats] = None) -> List[LineStats]:
            if node_key is None:
                # Return root nodes
                return [
                    line
                    for line in self.root_lines
                    if line.time and line.time >= min_time_s
                ]
            else:
                # Return children of the specified node
                return [
                    child
                    for child in node_key.childs
                    if child.time and child.time >= min_time_s
                ]

        # Define the node formatter function
        # Given a line, return its formatted string (displayed in the UI)
        def format_node(line: LineStats, indicator: str = "") -> str:
            filename = os.path.basename(line.file_name)
            line_id = f"{filename}::{line.function_name}::{line.line_no}"

            # Truncate source code
            truncated_source = (
                line.source[:40] + "..." if len(line.source) > 40 else line.source
            )

            # Format stats
            assert line.time is not None
            stats = f"[hits:{line.hits} time:{line.time:.2f}s]"

            # Return formatted line
            return f"{indicator}{line_id} {stats} - {truncated_source}"

        # Create and run the UI
        ui = TerminalTreeUI(get_tree_data, format_node)
        ui.run()
