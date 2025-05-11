from typing import List, Literal, Tuple, Optional, TypedDict, Union

from pydantic import BaseModel, Field, ConfigDict


class LineKey(BaseModel):
    file_name: str
    function_name: str
    line_no: Union[int, Literal["END_OF_FRAME"]]

    # makes it immutable and hashable
    model_config = ConfigDict(frozen=True)


class LineEvent(TypedDict):
    id: int
    file_name: str
    function_name: str
    line_no: Union[int, Literal["END_OF_FRAME"]]
    start_time: float
    stack_trace: list[Tuple[str, str, int]]


class LineStats(BaseModel):
    """Statistics for a single line of code."""

    model_config = ConfigDict(validate_assignment=True)

    id: int = Field(..., ge=0, description="Unique identifier for this line")

    # Key infos
    file_name: str = Field(..., min_length=1, description="File containing this line")
    function_name: str = Field(
        ..., min_length=1, description="Function containing this line"
    )
    line_no: Union[int, Literal["END_OF_FRAME"]] = Field(
        ..., description="Line number in the source file"
    )
    stack_trace: List[Tuple[str, str, int]] = Field(
        default_factory=list, description="Stack trace for this line"
    )

    # Stats
    start_time: float = Field(
        ..., ge=0, description="Time when this line was first executed"
    )
    hits: int = Field(..., ge=0, description="Number of times this line was executed")
    time: float = Field(
        description="Time spent on this line in milliseconds", default=0
    )

    # Source code
    source: str = Field(..., min_length=1, description="Source code for this line")

    # Parent line that called this function
    # If None then it
    parent: Optional[int] = None

    # Children lines called by this line (populated during analysis)
    # We use a dict because it alows us to remove some childs in O(1) time
    # We need to remove children when we merge duplicated and when we remove END_OF_FRAME events
    childs: dict[int, "LineStats"] = Field(default_factory=dict)

    @property
    def event_id(self) -> int:
        """Get the unique id for this line."""
        return self.id

    @property
    def event_key(self) -> Tuple[LineKey, Tuple[LineKey, ...]]:
        """Get the unique key for the event."""
        return (
            LineKey(
                file_name=self.file_name,
                function_name=self.function_name,
                line_no=self.line_no,
            ),
            tuple(
                LineKey(file_name=frame[0], function_name=frame[1], line_no=frame[2])
                for frame in self.stack_trace
            ),
        )
