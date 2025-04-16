import inspect
import logging
import sys
import time
import os
from typing import Dict, List, Tuple, Any
from .line_stats_tree import LineStatsTree

logging.basicConfig(level=logging.DEBUG)


class CodeTracer:
    def __init__(self):
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

    def trace_function(self, frame: Any, event: str, arg: Any) -> Any:
        # main function that will replace the default trace function
        # using sys.settrace

        # First thing to do is to return None as fast as possible if the code is not user code
        now = time.perf_counter()
        code = frame.f_code
        file_name = code.co_filename
        if not self._is_user_code(frame, file_name):
            self.last_time += time.perf_counter() - now
            return None
        # If the code is user code, we can continue

        line_no = frame.f_lineno
        func_name = code.co_name
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
        # Skip installed modules
        logging.debug(
            f"Tracing {event} {line_no} in {file_name} ({func_name}): {source} "
        )

        if event == "call":
            # A function is called
            if not self.tempo_line_infos:
                raise Exception("At this point we should have a tempo line infos")

            # We get info on who called the function
            # Using the tempo line infos instead of frame.f_back allows us to
            # get information about last parent that is from user code and not
            # from an imported / built in module
            caller_file = self.tempo_line_infos[0]
            caller_func = self.tempo_line_infos[1]
            caller_line = self.tempo_line_infos[2]
            caller_key = (caller_file, caller_func, caller_line)

            # Update call stack
            # Until we return from the function, all lines executed will have
            # the caller line as parent
            logging.debug(f" adding to stack: {caller_key}")
            self.call_stack.append(caller_key)

        elif event == "line" or event == "return":

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
                return self.trace_function

            # If we have a previous line, we can calculate the time elapsed for it and
            # add it to the tree
            elapsed = (now - self.last_time) * 1000

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
            self.last_time = now

            if event == "return":
                logging.debug(f" popping from stack: {self.call_stack[-1]}")

                # A function is returning
                # We just need to pop the last line from the call stack so newt
                # lines will have the correct parent
                if self.call_stack:
                    self.call_stack.pop()

                # We still need to update time and last infos for the next line
                self.last_time = now

        # We need to return the trace function to continue tracing
        # https://docs.python.org/3.8/library/sys.html#sys.settrace:~:text=The%20local%20trace%20function%20should
        return self.trace_function

    def start_tracing(self) -> None:
        # Reset state
        self.__init__()
        frame = sys._getframe().f_back
        while frame:
            frame.f_trace = self.trace_function
            self.botframe = frame
            frame = frame.f_back
        sys.settrace(self.trace_function)

    def stop_tracing(self) -> None:
        sys.settrace(None)

    def _is_user_code(self, frame: str, filename: str) -> bool:
        """Check if a file belongs to an installed module rather than user code.
        This is usd to determine if we want to trace a line or not"""
        # !!! This code is called for each line of external modules
        # It is very important to keep it as fast as possible to limit overhead

        site_packages_paths = [
            os.path.join(os.path.expanduser("~"), ".local/lib"),  # Local user packages
            "/usr/lib",  # System-wide packages
            "/usr/local/lib",  # Another common location
            "site-packages",  # Catch any other site-packages
            "frozen importlib",  # Frozen modules
            "frozen zipimport",  # Frozen zipimport modules
            "<",  # built-in modules
        ]
        for path in site_packages_paths:
            if path in filename:
                return False

        # We use this to not try to trace modules not written by the user
        module = inspect.getmodule(frame)
        if module is None:
            return False

        # Check if it's within the project directory
        project_dir = os.getcwd()

        # Check if file is in project directory but not in site-packages
        is_code_in_working_dir = (
            project_dir in filename
            and "site-packages" not in filename
            and "dist-packages" not in filename
        )

        return is_code_in_working_dir
