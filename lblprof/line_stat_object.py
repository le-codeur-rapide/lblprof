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
