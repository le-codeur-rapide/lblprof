"""Get values of line of codes to display them in the UI"""

from typing import Union, Literal
from functools import lru_cache


@lru_cache(maxsize=100)
def get_source_code(
    file_name: str, line_no: Union[int, Literal["END_OF_FRAME"]]
) -> str:
    """Get the source code for a specific line in a file."""
    if line_no == "END_OF_FRAME":
        return "END_OF_FRAME"
    try:
        with open(file_name, "r") as f:
            lines = f.readlines()
            return lines[line_no - 1].strip()
    except Exception:
        return "No source code found"
