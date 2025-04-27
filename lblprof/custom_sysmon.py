import logging
import sys
import time
from typing import List, Tuple
from .line_stats_tree import LineStatsTree


# Check if sys.monitoring is available (Python 3.12+)
if not hasattr(sys, "monitoring"):
    raise ImportError("sys.monitoring is not available. This requires Python 3.12+")


class CodeMonitor:
    """
    This class uses the sys.monitoring API (Python 3.12+) to register execution time for each line of code.
    It will create a monitore the infos of the execution time for each line of code, keeping track of the frame (the function / module)
    that called it.
    The goal of thsi class is to store the infos as fast as possible to have as few overhead as possible.  All the computation and storage is
    done during the build_tree metho of the tree class
    """

    def __init__(self):
        # Define a unique monitoring tool ID
        self.tool_id = sys.monitoring.PROFILER_ID

        # Call stack to store callers and keep track of the functions that called the current frame
        self.call_stack: List[Tuple[str, str, int]] = []

        # Data structure to store the infos, insert should be quick during tracing, compute should be delayed at build time
        self.tree = LineStatsTree()

        # Use to store the line info until next line to keep track of who is the caller during call events
        self.tempo_line_infos = None

        # We use this to store the overhead of the monitoring tool and deduce it from the total time
        # The time of execution of the program will still be longer but at least the displayed time will be
        # more accurate
        self.overhead = 0

        # Total number of events, used to generate unique ids for each line
        self.total_events = 0

    def _handle_call(self, code, instruction_offset):
        """Handle function call events"""
        start = time.perf_counter()
        file_name = code.co_filename

        if not self._is_user_code(file_name):
            # The call is from an imported module, we deactivate monitoring for this function
            sys.monitoring.set_local_events(self.tool_id, code, 0)
            self.overhead += time.perf_counter() - start
            return

        func_name = code.co_name
        line_no = code.co_firstlineno
        # We entered a frame from user code, we activate monitoring for it
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
            # Here we are called by a root line, so no caller in the stack
            return

        # caller_key is a tuple of (caller_file, caller_func, caller_line_no)
        caller_key = self.tempo_line_infos

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

        # Add the line record to the tree
        logging.debug(f"tracing line: {file_name} {func_name} {line_no}")
        self.tree.add_line_event(
            id=self.total_events,
            file_name=file_name,
            function_name=func_name,
            line_no=line_no,
            # We substract the overhead to simulate a raw run without tracing
            start_time=now - self.overhead,
            stack_trace=self.call_stack.copy(),
        )
        self.tempo_line_infos = (file_name, func_name, line_no)
        self.total_events += 1

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

        # In case the stop_tracing is called from a lower frame than start_tracing,
        # we need to activate monitoring for the returned frame
        current_frame = sys._getframe().f_back.f_back
        if not sys.monitoring.get_tool(self.tool_id):
            sys.monitoring.use_tool_id(self.tool_id, "lblprof-monitor")
        sys.monitoring.set_local_events(
            self.tool_id,
            current_frame.f_code,
            sys.monitoring.events.LINE
            | sys.monitoring.events.PY_RETURN
            | sys.monitoring.events.PY_START,
        )

        # Adding a END_OF_FRAME event to the tree to mark the end of the frame
        # This is used to compute the duration of the last line of the frame
        self.tree.add_line_event(
            id=self.total_events,
            file_name=file_name,
            function_name=func_name,
            line_no="END_OF_FRAME",
            start_time=now,
            stack_trace=self.call_stack.copy(),
        )

        # A function is returning
        # We just need to pop the last line from the call stack so next
        # lines will have the correct parent
        if self.call_stack:
            self.call_stack.pop()

        self.total_events += 1

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

        # 2 f_back to get out of the "start_tracing" function stack and get the user code frame
        current_frame = sys._getframe().f_back.f_back

        # The idea is that we register for calls at global level to not miss future calls and we register
        # for lines at the current frame (take care of set_local so it can be removed)
        sys.monitoring.set_events(self.tool_id, sys.monitoring.events.PY_START)
        sys.monitoring.set_local_events(
            self.tool_id,
            current_frame.f_code,
            sys.monitoring.events.LINE | sys.monitoring.events.PY_RETURN,
        )
        logging.debug("Tracing started")

    def stop_tracing(self) -> None:
        # Turn off monitoring for our tool
        sys.monitoring.set_events(self.tool_id, 0)
        current_frame = sys._getframe()
        while current_frame:
            if not sys.monitoring.get_tool(self.tool_id):
                sys.monitoring.use_tool_id(self.tool_id, "lblprof-monitor")
                sys.monitoring.set_events(self.tool_id, 0)
            sys.monitoring.set_local_events(self.tool_id, current_frame.f_code, 0)
            sys.monitoring.free_tool_id(self.tool_id)
            current_frame = current_frame.f_back

    def _is_user_code(self, filename: str) -> bool:
        """Check if a file belongs to an installed module rather than user code.
        This is used to determine if we want to trace a line or not"""

        if (
            ".local/lib" in filename
            or "/usr/lib" in filename
            or "/usr/local/lib" in filename
            or "site-packages" in filename
            or "dist-packages" in filename
            or "/lib/python3.12/" in filename
            or "frozen" in filename
            or filename.startswith("<")
        ):
            return False
        return True
