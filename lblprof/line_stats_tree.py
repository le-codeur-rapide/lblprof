import logging
import os
from typing import List, Dict, Literal, Tuple, Optional, Union
from lblprof.curses_ui import TerminalTreeUI
from lblprof.line_stat_object import LineStats, LineKey, LineEvent


class LineStatsTree:
    """A tree structure to manage LineStats objects with automatic parent-child time propagation."""

    def __init__(self):
        # just raw event from custom_tracer
        # Inserting in this list should be as fast as possible to avoid overhead
        self.raw_events_list: List[LineEvent] = []

        # Index of events by id
        self.events_index: Dict[int, LineStats] = {}

        # Track root nodes (lines of user code initial frame)
        self.root_lines: List[LineStats] = []

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
        # We don't want to add events from stop_tracing function
        # We might want something cleaner ?
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

    def build_tree(self) -> None:
        """Build the tree (self.events_index) from the raw events list."""

        # 1. Build the events index (id: LineStats)
        for event in self.raw_events_list:
            source = self._get_source_code(event["file_name"], event["line_no"])
            if "stop_tracing" in source:
                # This allow to delete the call to stop_tracing from the tree
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
                    source=source,
                )
            else:
                raise Exception("Event key already in self.events_index")

        # 2. Establish parent-child relationships
        # We first build a dict to map event keys to event ids, so we can get the parent_id in O(1) time for each line
        # we reverse the list because we always prefer that the parent of a line is the first event corresponding to the parent line
        linekey_to_id = {
            line.event_key[0]: event_id
            for event_id, line in reversed(list(self.events_index.items()))
        }
        for id, event in self.events_index.items():

            # We get parent from stack trace
            if len(event.stack_trace) == 0:
                # we are in a root line
                self.root_lines.append(event)
                continue

            # find id of the parent in self.events_index
            parent_key = LineKey(
                file_name=event.stack_trace[-1][0],
                function_name=event.stack_trace[-1][1],
                line_no=event.stack_trace[-1][2],
            )
            parent_id = linekey_to_id.get(parent_key)
            if parent_id is None:
                raise Exception(
                    f"Parent key {event.stack_trace[-1]} not found in events index"
                )

            self.events_index[parent_id].childs[id] = event
            event.parent = parent_id
            self.events_index[id] = event

        # 3. Update duration of each line
        # we use the time_save dict to store the id and start time of the previous line in the same frame (which is not necessary the previous line in the index)
        time_save: Dict[Union[int, None], Tuple[int, float]] = {}
        for id, event in self.events_index.items():
            if event.parent not in time_save:
                # first line of the frame
                time_save[event.parent] = (id, event.start_time)
                continue
            # not the first line of the frame, update the time of the previous line
            previous_id, previous_start_time = time_save[event.parent]
            if event.start_time - previous_start_time < 0:
                logging.warning(
                    f"Time of line {event.id} is negative: {event.start_time} - {previous_start_time}"
                )
            self.events_index[previous_id].time = event.start_time - previous_start_time
            time_save[event.parent] = (id, event.start_time)

        # 4. Remove END_OF_FRAME lines
        # The END_OF_FRAME lines are not needed in the tree anymore
        for id, event in list(self.events_index.items()):
            if event.line_no == "END_OF_FRAME":
                parent_id = event.parent
                if parent_id is not None:
                    del self.events_index[parent_id].childs[id]
                del self.events_index[id]
        self.root_lines = [
            line for line in self.events_index.values() if line.parent is None
        ]

        # 5. Merge lines that have same file_name, function_name and line_no (to avoid duplicates in a for loop for example)
        # Not it is important to start by root nodes and merge going down the tree (DFS pre-order)
        grouped_events = {}

        def _merge(event: LineStats):
            """Merge events that have same file_name, function_name and line_no in the same frame."""
            key = (
                event.file_name,
                event.function_name,
                event.line_no,
                tuple(event.stack_trace),
            )
            if key not in grouped_events:
                grouped_events[key] = event
            else:
                grouped = grouped_events[key]
                grouped.time += event.time
                grouped.hits += event.hits
                grouped.childs.update(event.childs)
                # update parent of the new children
                for child in event.childs.values():
                    child.parent = grouped.id

            # Now recurse on the children
            for child in event.childs.values():
                _merge(child)

        for event in self.root_lines:
            _merge(event)

        # 6. Update the events_index with the merged events
        self.events_index = {}
        for key, event in grouped_events.items():
            self.events_index[event.id] = event

        # 7. Update the childs attributes to remove deleted childs
        for id, event in self.events_index.items():
            event.childs = {
                child.id: child
                for child in event.childs.values()
                if child.id in self.events_index
            }
        self.root_lines = [
            line for line in self.events_index.values() if line.parent is None
        ]

    # --------------------------------
    # Display methods
    # One method to print the tree in the console
    # One method to display the tree in an interactive terminal interface
    # --------------------------------
    def display_tree(
        self,
        root_key: Optional[int] = None,
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
            children: dict[int, LineStats],
        ) -> Dict[str, List[LineStats]]:
            children_by_file = {}
            for child in children.values():
                if child.file_name not in children_by_file:
                    children_by_file[child.file_name] = []
                children_by_file[child.file_name].append(child)

            # Sort each file's lines by line number
            for file_name in children_by_file:
                children_by_file[file_name].sort(key=lambda x: x.line_no)

            return children_by_file

        def get_all_children(
            children_by_file: Dict[str, List[LineStats]],
        ) -> List[LineStats]:
            all_children = []
            for file_name in children_by_file:
                all_children.extend(children_by_file[file_name])
            return all_children

        if root_key:

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
                    for child in node_key.childs.values()
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

    # --------------------------------
    # Private methods
    # --------------------------------
    def _save_events(self) -> None:
        """Save the events to a file."""
        with open("events.csv", "w") as f:
            for event in self.raw_events_list:
                f.write(
                    f"{event['id']},{event['file_name']},{event['function_name']},{event['line_no']},{event['start_time']},{event['stack_trace']}\n"
                )

    def _save_events_index(self) -> None:
        """Save the events index to a file."""
        with open("events_index.csv", "w") as f:
            for key, event in self.events_index.items():
                f.write(
                    f"{event.id},{event.file_name.split('/')[-1]},{event.function_name},{event.line_no},{event.source},{event.hits},{event.start_time},{event.time},{len(event.childs)},{event.parent}\n"
                )

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
