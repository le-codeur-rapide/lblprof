import logging
import sys
import time
import os
from typing import Dict, List, Tuple
from .line_stats_tree import LineStatsTree

logging.basicConfig(level=logging.DEBUG)

# Check if sys.monitoring is available (Python 3.12+)
if not hasattr(sys, "monitoring"):
    raise ImportError("sys.monitoring is not available. This requires Python 3.12+")


class CodeMonitor:
    """
    A code monitor using the sys.monitoring API (Python 3.12+)
    """

    def __init__(self):
        # Define a unique monitoring tool ID
        self.tool_id = sys.monitoring.PROFILER_ID

        # We use a dictionary to store the source code of lines
        self.line_source: Dict[Tuple[str, str, int], str] = {}
        # Call stack to handle nested calls
        self.call_stack: List[Tuple[str, str, int]] = []
        # Current line tracking
        self.last_time: float = time.perf_counter()
        # We use this to store the tree of line stats
        self.tree = LineStatsTree()
        # Use to store the line info until next line to have the time of the line
        self.tempo_line_infos = None
        self.count = 0
        self.site_packages_paths = [
            os.path.join(os.path.expanduser("~"), ".local/lib"),  # Local user packages
            "/usr/lib",  # System-wide packages
            "/usr/local/lib",  # Another common location
            "site-packages",  # Catch any other site-packages
            "frozen importlib",  # Frozen modules
            "frozen zipimport",  # Frozen zipimport modules
            "<",  # built-in modules
        ]
        self.overhead = 0

    def _handle_call(self, code, instruction_offset):
        """Handle function call events"""
        start = time.perf_counter()
        file_name = code.co_filename

        # Skip if not user code
        if not self._is_user_code(file_name):
            sys.monitoring.set_local_events(self.tool_id, code, 0)
            self.overhead += time.perf_counter() - start
            return

        func_name = code.co_name
        line_no = code.co_firstlineno
        sys.monitoring.set_local_events(
            self.tool_id,
            code,
            sys.monitoring.events.LINE
            | sys.monitoring.events.PY_RETURN
            | sys.monitoring.events.PY_START,
        )

        logging.debug(
            f"handle call: filename: {file_name}, func_name: {func_name}, line_no: {line_no}"
        )
        # We get info on who called the function
        # Using the tempo line infos instead of frame.f_back allows us to
        # get information about last parent that is from user code and not
        # from an imported / built in module
        if not self.tempo_line_infos:
            return

        caller_file = self.tempo_line_infos[0]
        caller_func = self.tempo_line_infos[1]
        caller_line = self.tempo_line_infos[2]
        caller_key = (caller_file, caller_func, caller_line)

        # Update call stack
        # Until we return from the function, all lines executed will have
        # the caller line as parent
        self.call_stack.append(caller_key)

    def _handle_line(self, code, line_number):
        """Handle line execution events"""
        now = time.perf_counter()

        file_name = code.co_filename
        func_name = code.co_name
        line_no = line_number

        # Get time and create key
        line_key = (file_name, func_name, line_no)

        # Get or store source code of the line
        if line_key not in self.line_source:
            try:
                with open(file_name, "r") as f:
                    source_lines = f.readlines()
                    source = (
                        source_lines[line_no - 1].strip()
                        if 0 <= line_no - 1 < len(source_lines)
                        else "<line not available>"
                    )
                    self.line_source[line_key] = source
            except Exception:
                self.line_source[line_key] = "<source not available>"
        source = self.line_source[line_key]

        # Skip if not user code
        if not self._is_user_code(file_name):
            self.overhead += time.perf_counter() - now
            return sys.monitoring.DISABLE
        logging.debug(f"Tracing line {line_no} in {file_name} ({func_name}): {source}")

        # If there are no call in the stack, we setup a placeholder for
        # the root of the tree
        parent_key = self.call_stack[-1] if self.call_stack else None
        if not self.tempo_line_infos:
            # This is the first line executed, there is no new duration to store in the tree,
            # we just store the current line info
            self.tempo_line_infos = (
                file_name,
                func_name,
                line_no,
                source,
                parent_key,
            )
            return

        # If we have a previous line, we can calculate the time elapsed for it and
        # add it to the tree
        print(f"self.overhead: {self.overhead}")
        print(f"now - self.last_time: {now - self.last_time}")
        elapsed = (now - self.last_time - self.overhead) * 1000

        self.tree.update_line_event(
            file_name=self.tempo_line_infos[0],
            function_name=self.tempo_line_infos[1],
            line_no=self.tempo_line_infos[2],
            # We do that because if the function has no return, the last line will be
            # treated twice for event line and call, in terms of duration it will be
            # the same but we have to make sure hit is 1 in total
            hits=(
                0
                if self.tempo_line_infos[2] == line_no
                and self.tempo_line_infos[1] == func_name
                and self.tempo_line_infos[0] == file_name
                else 1
            ),
            time_ms=elapsed,
            source=self.tempo_line_infos[3],
            parent_key=self.tempo_line_infos[4],
        )

        # Store current line info for next line + reset last_time
        self.tempo_line_infos = (file_name, func_name, line_no, source, parent_key)
        self.last_time = time.perf_counter()
        self.overhead = 0

    def _handle_return(self, code, instruction_offset, retval):
        """Handle function return events"""
        now = time.perf_counter()

        file_name = code.co_filename
        func_name = code.co_name
        line_no = code.co_firstlineno

        # Skip if not user code
        if not self._is_user_code(file_name):
            self.overhead += time.perf_counter() - now
            return sys.monitoring.DISABLE
        logging.debug(f"Returning from {func_name} in {file_name} ({line_no})")

        # A function is returning
        # We just need to pop the last line from the call stack so next
        # lines will have the correct parent
        if self.call_stack:
            self.call_stack.pop()

        # We still need to update time for the next line
        self.tempo_line_infos = None

    def start_tracing(self) -> None:
        # Reset state
        self.__init__()
        sys.monitoring.use_tool_id(self.tool_id, "lblprof-monitor")

        # Register our callback functions
        sys.monitoring.register_callback(
            self.tool_id, sys.monitoring.events.PY_START, self._handle_call
        )
        sys.monitoring.register_callback(
            self.tool_id, sys.monitoring.events.LINE, self._handle_line
        )
        sys.monitoring.register_callback(
            self.tool_id, sys.monitoring.events.PY_RETURN, self._handle_return
        )

        # Turn on monitoring for all events we're interested in
        current_frame = (
            sys._getframe().f_back.f_back
        )  # 2 f_back to get out of the function call
        logging.debug(f"info on current frame: {current_frame.f_code}")
        logging.debug(f"info on current frame: {current_frame.f_code.co_filename}")
        logging.debug(f"info on current frame: {current_frame.f_code.co_name}")
        logging.debug(f"info on current frame: {current_frame.f_code.co_firstlineno}")
        # The idea is that we register for calls at global level to not miss future calls and we register for lines at the current frame (take care of set_local so it can be removed)
        sys.monitoring.set_events(self.tool_id, sys.monitoring.events.PY_START)
        sys.monitoring.set_local_events(
            # sys.monitoring.set_events(
            self.tool_id,
            current_frame.f_code,
            # sys.monitoring.events.PY_START
            sys.monitoring.events.LINE | sys.monitoring.events.PY_RETURN,
        )

        logging.debug("Tracing started")

    def stop_tracing(self) -> None:
        # Turn off monitoring for our tool
        sys.monitoring.set_events(self.tool_id, 0)
        sys.monitoring.free_tool_id(self.tool_id)

    def _is_user_code(self, filename: str) -> bool:
        """Check if a file belongs to an installed module rather than user code.
        This is used to determine if we want to trace a line or not"""

        if (
            ".local/lib" in filename
            or "/usr/lib" in filename
            or "/usr/local/lib" in filename
            or "site-packages" in filename
            or "dist-packages" in filename
            or "frozen" in filename
            or filename.startswith("<")
        ):
            return False
        return True
