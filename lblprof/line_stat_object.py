from typing import List, Tuple, Optional

from pydantic import BaseModel, Field, ConfigDict


class LineStats(BaseModel):
    """Statistics for a single line of code."""

    model_config = ConfigDict(validate_assignment=True)

    file_name: str = Field(..., min_length=1, description="File containing this line")
    function_name: str = Field(
        ..., min_length=1, description="Function containing this line"
    )
    line_no: int = Field(..., ge=1, description="Line number in the source file")
    hits: int = Field(..., ge=0, description="Number of times this line was executed")
    time: float = Field(
        ..., ge=0, description="Time spent on this line in milliseconds"
    )
    avg_time: float = Field(
        ..., ge=0, description="Average time per hit in milliseconds"
    )
    source: str = Field(..., min_length=1, description="Source code for this line")
    child_time: float = Field(
        default=0.0, ge=0, description="Time spent in called lines"
    )

    # Parent line that called this function
    # If None then it
    parent_key: Optional[Tuple[str, str, int]] = None

    # Children lines called by this line (populated during analysis)
    child_keys: List[Tuple[str, str, int]] = Field(default_factory=list)

    @property
    def key(self) -> Tuple[str, str, int]:
        """Get the unique key for this line."""
        return (self.file_name, self.function_name, self.line_no)

    @property
    def extended_key(self) -> Tuple:
        """Get an extended unique key that includes parent information."""
        return (self.file_name, self.function_name, self.line_no, self.parent_key)

    @property
    def self_time(self) -> float:
        """Get time spent on this line excluding child calls."""
        return max(0.0, self.time - self.child_time)

    @property
    def total_time(self) -> float:
        """Get total time including child calls."""
        return self.time
