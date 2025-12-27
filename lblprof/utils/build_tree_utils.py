from lblprof.line_stat_object import EventKeyT, LineEvent, LineKey, LineStats
from lblprof.utils.source_code_utils import get_source_code


def build_event_index(events: list[LineEvent]) -> dict[int, LineStats]:
    """Build an index of events (id: LineStats) from a list of events.
    First version:
    - Use id as key and get source code from file name and line number"""
    events_index: dict[int, LineStats] = {}
    for event in events:
        source = get_source_code(event.file_name, event.line_no)

        event_key = event.id
        if event_key in events_index:
            msg = "Event key already in events_index"
            raise ValueError(msg)
        events_index[event_key] = LineStats(
            **event.__dict__,
            hits=1,
            source=source,
            id_childs_dict={},
            parent=None,
            duration=0,
        )
    return events_index


def establish_parent_child_relationships(
    events_index: dict[int, LineStats],
) -> None:
    """Establish parent-child relationships for events"""
    # We first build a dict to map event keys to event ids, so we can get the
    # parent_id in O(1) time for each line
    # we reverse the list because we always prefer that the parent of a line is the
    # first event corresponding to the parent line
    linekey_to_id = {
        line.event_key[0]: event_id
        for event_id, line in reversed(list(events_index.items()))
    }
    for event_id, event in events_index.items():
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

        events_index[parent_id].id_childs_dict[event_id] = event
        event.parent = parent_id
        events_index[event_id] = event


def establish_line_durations(
    events_index: dict[int, LineStats],
) -> None:
    """Establish line durations for events"""
    # we use the time_save dict to store the id and start time of the previous line
    # in the same frame (which is not necessary the previous line in the index)
    time_save: dict[int | None, tuple[int, float]] = {}
    for event_id, event in events_index.items():
        if event.parent not in time_save:
            # first line of the frame
            time_save[event.parent] = (event_id, event.start_time)
            continue
        # not the first line of the frame, update the time of the previous line
        previous_id, previous_start_time = time_save[event.parent]
        events_index[previous_id].duration = event.start_time - previous_start_time
        time_save[event.parent] = (event_id, event.start_time)


def clear_end_of_frame_events(
    events_index: dict[int, LineStats],
) -> None:
    """Clear END_OF_FRAME events"""
    for event_id, event in list(events_index.items()):
        if event.line_no == "END_OF_FRAME":
            parent_id = event.parent
            if parent_id is not None:
                del events_index[parent_id].id_childs_dict[event_id]
            del events_index[event_id]


def merge_similar_lines(events_index: dict[int, LineStats]) -> dict[int, LineStats]:
    """Merge lines that have same file_name, function_name and line_no"""
    root_lines = [line for line in events_index.values() if line.parent is None]
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
            grouped.id_childs_dict.update(event.id_childs_dict)
            # update parent of the new children
            for child in event.childs:
                child.parent = grouped.id

        # Now recurse on the children
        for child in event.childs:
            _merge(child)

    for event in root_lines:
        _merge(event)

    for event in grouped_events.values():
        events_index[event.id] = event


def remove_deleted_childs_from_childs_attributes(
    events_index: dict[int, LineStats],
) -> None:
    for event in events_index.values():
        event.id_childs_dict = {
            child.id: child for child in event.childs if child.id in events_index
        }
