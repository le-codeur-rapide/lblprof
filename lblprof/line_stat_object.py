from typing import List, Tuple, Optional, TypedDict

from pydantic import BaseModel, Field, ConfigDict


class LineKey(BaseModel):
    file_name: str
    function_name: str
    line_no: int

    class Config:
        frozen = True  # makes it immutable and hashable


class LineEvent(TypedDict):
    file_name: str
    function_name: str
    line_no: int
    start_time: float
    stack_trace: list[Tuple[str, str, int]]


class LineStats(BaseModel):
    """Statistics for a single line of code."""

    model_config = ConfigDict(validate_assignment=True)

    # Key infos
    file_name: str = Field(..., min_length=1, description="File containing this line")
    function_name: str = Field(
        ..., min_length=1, description="Function containing this line"
    )
    line_no: int = Field(..., ge=0, description="Line number in the source file")
    stack_trace: List[Tuple[str, str, int]] = Field(
        default_factory=list, description="Stack trace for this line"
    )

    # Stats
    start_time: float = Field(
        ..., ge=0, description="Time when this line was first executed"
    )
    hits: int = Field(..., ge=0, description="Number of times this line was executed")
    time: Optional[float] = Field(
        ge=0, description="Time spent on this line in milliseconds", default=None
    )
    avg_time: Optional[float] = Field(
        ge=0, description="Average time per hit in milliseconds", default=None
    )

    # Source code
    source: str = Field(..., min_length=1, description="Source code for this line")

    # Parent line that called this function
    # If None then it
    parent: Optional[Tuple[LineKey, Tuple[LineKey, ...]]] = None

    # Children lines called by this line (populated during analysis)
    childs: List["LineStats"] = Field(default_factory=list)

    @property
    def event_key(self) -> Tuple[LineKey, Tuple[LineKey, ...]]:
        """Get the unique key for this line."""
        return (
            LineKey(
                file_name=self.file_name,
                function_name=self.function_name,
                line_no=self.line_no,
            ),
            tuple(
                LineKey(
                    file_name=key[0],
                    function_name=key[1],
                    line_no=key[2],
                )
                for key in self.stack_trace
            ),
        )
