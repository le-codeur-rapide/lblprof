"""Get values of line of codes to display them in the UI"""

from functools import lru_cache
from pathlib import Path
from typing import Literal


@lru_cache(maxsize=100)
def get_source_code(
    file_name: str,
    line_no: int | Literal["END_OF_FRAME"],
) -> str:
    """Get the source code for a specific line in a file."""
    if line_no == "END_OF_FRAME":
        return "END_OF_FRAME"
    try:
        with Path(file_name).open() as f:
            lines = f.readlines()
            return lines[line_no - 1].strip()
    except Exception:
        return "No source code found"


def truncate_line(line: str, max_length: int) -> str:
    """Truncate the line to a maximum length."""
    return line[: max_length - 3] + "..." if len(line) > max_length else line
