from pathlib import Path

from lblprof.line_stat_object import EventKeyT, LineEvent, LineKey, LineStats
from lblprof.utils.source_code_utils import get_source_code


class LineStatsTree:
    """A tree structure to manage LineStats objects with automatic parent-child time
    propagation."""

    def __init__(self, line_events: list[LineEvent]) -> None:
        # just raw event from custom_tracer
        # Inserting in this list should be as fast as possible to avoid overhead
        self.raw_events_list: list[LineEvent] = line_events

        # Index of events by id
        self.events_index: dict[int, LineStats] = {}

        # Track root nodes (lines of user code initial frame)
        self.root_lines: list[LineStats] = []

        # cache of source code for lines
        # key is (file_name, line_no) for a source code line
        self.line_source: dict[tuple[str, int], str] = {}

    def build_tree(self) -> None:
        """Build the tree (self.events_index) from the raw events list."""

        # 1. Build the events index (id: LineStats)
        for event in self.raw_events_list:
            source = get_source_code(event.file_name, event.line_no)

            event_key = event.id
            if event_key not in self.events_index:
                self.events_index[event_key] = LineStats(
                    **event.__dict__,
                    hits=1,
                    source=source,
                    childs={},
                    parent=None,
                    duration=0,
                )
            else:
                msg = "Event key already in self.events_index"
                raise ValueError(msg)

        # 2. Establish parent-child relationships
        # We first build a dict to map event keys to event ids, so we can get the
        # parent_id in O(1) time for each line
        # we reverse the list because we always prefer that the parent of a line is the
        # first event corresponding to the parent line
        linekey_to_id = {
            line.event_key[0]: event_id
            for event_id, line in reversed(list(self.events_index.items()))
        }
        for event_id, event in self.events_index.items():
            # We get parent from stack trace
            if len(event.call_stack) == 0:
                continue

            # find id of the parent in self.events_index
            parent_key = LineKey(
                file_name=event.call_stack[-1][0],
                function_name=event.call_stack[-1][1],
                line_no=event.call_stack[-1][2],
            )
            parent_id = linekey_to_id.get(parent_key)
            if parent_id is None:
                msg = f"Parent key {event.call_stack[-1]} not found in events index"
                raise ValueError(msg)

            self.events_index[parent_id].childs[event_id] = event
            event.parent = parent_id
            self.events_index[event_id] = event
        # 3. Update duration of each line
        # we use the time_save dict to store the id and start time of the previous line
        # in the same frame (which is not necessary the previous line in the index)
        time_save: dict[int | None, tuple[int, float]] = {}
        for event_id, event in self.events_index.items():
            if event.parent not in time_save:
                # first line of the frame
                time_save[event.parent] = (event_id, event.start_time)
                continue
            # not the first line of the frame, update the time of the previous line
            previous_id, previous_start_time = time_save[event.parent]
            self.events_index[previous_id].duration = (
                event.start_time - previous_start_time
            )
            time_save[event.parent] = (event_id, event.start_time)

        # 4. Remove END_OF_FRAME lines
        # The END_OF_FRAME lines are not needed in the tree anymore
        for event_id, event in list(self.events_index.items()):
            if event.line_no == "END_OF_FRAME":
                parent_id = event.parent
                if parent_id is not None:
                    del self.events_index[parent_id].childs[event_id]
                del self.events_index[event_id]
        self.root_lines = [
            line for line in self.events_index.values() if line.parent is None
        ]

        # 5. Merge lines that have same file_name, function_name and line_no (to avoid
        # duplicates in a for loop for example)
        # Note it is important to start by root nodes and merge going down the tree (DFS
        # pre-order)
        grouped_events: dict[EventKeyT, LineStats] = {}

        def _merge(event: LineStats) -> None:
            """Merge events that have same file_name, function_name and line_no in the
            same frame.
            """
            key = (
                LineKey(event.file_name, event.func_name, event.line_no),
                tuple(event.call_stack),
            )
            if key not in grouped_events:
                grouped_events[key] = event
            else:
                grouped = grouped_events[key]
                grouped.duration += event.duration
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
        for event in grouped_events.values():
            self.events_index[event.id] = event

        # 7. Update the childs attributes to remove deleted childs
        for event in self.events_index.values():
            event.childs = {
                child.id: child
                for child in event.childs.values()
                if child.id in self.events_index
            }
        self.root_lines = [
            line for line in self.events_index.values() if line.parent is None
        ]
        self._save_events_index()

    # --------------------------------
    # Private methods
    # --------------------------------
    def _save_events(self) -> None:
        """Save the events to a file."""
        with Path("events.csv").open("w") as f:
            f.writelines(
                f"{event.id},{event.file_name},{event.func_name},{event.line_no},{event.start_time},{event.call_stack}\n"
                for event in self.raw_events_list
            )

    def _save_events_index(self) -> None:
        """Save the events index to a file."""
        with Path("events_index.csv").open("w") as f:
            f.writelines(
                f"{event.id},{event.file_name.split('/')[-1]},{event.func_name},{event.line_no},{event.source},{event.hits},{event.start_time},{event.duration},{len(event.childs)},{event.parent}\n"
                for _, event in self.events_index.items()
            )
