import csv
from typing import Literal, NamedTuple, Optional, Tuple
from dataclasses import dataclass


class LineKey(NamedTuple):
    file_name: str
    function_name: str
    line_no: int | Literal["END_OF_FRAME"]


@dataclass
class LineEvent:
    id: int
    file_name: str
    func_name: str
    line_no: int | Literal["END_OF_FRAME"]
    start_time: float
    call_stack: list[LineKey]


EventKeyT = Tuple[LineKey, Tuple[LineKey, ...]]


@dataclass
class LineStats(LineEvent):
    """Statistic of the line of code"""

    # Number of times this line was executed
    hits: int
    # The source code of the line
    source: str
    childs: dict[int, "LineStats"]
    parent: Optional[int]
    duration: float

    @property
    def event_key(self) -> EventKeyT:
        """Get the unique key for the event."""
        return (
            LineKey(
                file_name=self.file_name,
                function_name=self.func_name,
                line_no=self.line_no,
            ),
            tuple(
                LineKey(file_name=frame[0], function_name=frame[1], line_no=frame[2])
                for frame in self.call_stack
            ),
        )


def save_events_csv(events: list[LineEvent], path: str = "events.csv"):
    """Helper function that saves list of LineEvents to csv"""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["id", "file_name", "func_name", "line_no", "start_time", "stack_trace"]
        )

        for ev in events:
            writer.writerow(
                [
                    ev.id,
                    ev.file_name,
                    ev.func_name,
                    ev.line_no,
                    ev.start_time,
                    ";".join(
                        f"{lk.file_name}:{lk.function_name}:{lk.line_no}"
                        for lk in ev.call_stack
                    ),
                ]
            )
