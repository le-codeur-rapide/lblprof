from pathlib import Path

from lblprof.line_stat_object import LineEvent, LineStats
from lblprof.utils.build_tree_utils import (
    build_event_index,
    clear_end_of_frame_events,
    establish_line_durations,
    establish_parent_child_relationships,
    merge_similar_lines,
    remove_deleted_childs_from_childs_attributes,
)


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
        events_index = build_event_index(self.raw_events_list)

        # 2. Establish parent-child relationships
        establish_parent_child_relationships(events_index)

        # 3. Update duration of each line
        establish_line_durations(events_index)

        # 4. Remove END_OF_FRAME lines
        # The END_OF_FRAME lines are not needed in the tree anymore
        clear_end_of_frame_events(events_index)

        # 5. Merge lines that have same file_name, function_name and line_no (to avoid
        # duplicates in a for loop for example)
        merge_similar_lines(events_index)

        # 6. Update the childs attributes to remove deleted childs
        remove_deleted_childs_from_childs_attributes(events_index)

        self.root_lines = [
            line for line in events_index.values() if line.parent is None
        ]
        self.events_index = events_index
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
