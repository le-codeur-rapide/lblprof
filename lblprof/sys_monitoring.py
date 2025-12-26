import logging
import sys
import time
from types import CodeType

from lblprof.line_stat_object import LineEvent, LineKey
from lblprof.line_stats_tree import LineStatsTree

TOOL_ID = sys.monitoring.PROFILER_ID
PROFILER_NAME = "lblprof-monitor"
EVENTS = (
    sys.monitoring.events.LINE
    | sys.monitoring.events.PY_RETURN
    | sys.monitoring.events.PY_START
)


class CodeMonitor:
    """Time and record sys.monitoring events"""

    def __init__(self) -> None:
        self.stack: list[LineKey] = []
        """the stack is used to stock list of function calls that led to the
        current line"""
        self.events: list[LineEvent] = []
        self.nb_events_recorded: int = 0
        self.last_line_infos: LineKey | None = None
        self.tree: LineStatsTree = LineStatsTree([])

    def handle_call(
        self,
        code: CodeType,
        instruction_offset: int,
    ) -> None:
        """Code to execute when a function is called"""
        logging.debug(f"CALL in {code.co_name} at offset {instruction_offset}")
        if not self.last_line_infos:
            # Here we are called by a root line, so no caller in the stack
            return
        caller_key = self.last_line_infos
        self.stack.append(caller_key)

    def handle_line(
        self,
        code: CodeType,
        instruction_offset: int,
    ) -> None:
        """Code to run when a line of code is executed"""
        logging.debug(f"LINE in {code.co_name}, at offset {instruction_offset}")
        self.events.append(
            LineEvent(
                id=self.nb_events_recorded,
                file_name=code.co_filename,
                func_name=code.co_name,
                line_no=instruction_offset,
                call_stack=self.stack.copy(),
                start_time=time.perf_counter(),
            ),
        )
        self.last_line_infos = LineKey(
            code.co_filename,
            code.co_name,
            instruction_offset,
        )
        self.nb_events_recorded += 1

    def handle_return(
        self,
        code: CodeType,
        instruction_offset: int,
        retval: object,  # noqa: ARG002
    ) -> None:
        """Code to run when a function is returned"""
        logging.debug(f"RETURN from {code.co_name} at offset {instruction_offset}")
        self.events.append(
            LineEvent(
                id=self.nb_events_recorded,
                file_name=code.co_filename,
                func_name=code.co_name,
                line_no="END_OF_FRAME",
                call_stack=self.stack.copy(),
                start_time=time.perf_counter(),
            ),
        )
        if self.stack:
            self.stack.pop()

        self.nb_events_recorded += 1

    def register_hooks(self, tool_id: int = TOOL_ID) -> None:
        """Create sys monitoring tool and add the different handlers"""
        # register tool callbacks if not already registered
        if not sys.monitoring.get_tool(tool_id):
            sys.monitoring.use_tool_id(tool_id, PROFILER_NAME)
        sys.monitoring.register_callback(
            tool_id,
            sys.monitoring.events.PY_START,
            self.handle_call,
        )
        sys.monitoring.register_callback(
            tool_id,
            sys.monitoring.events.LINE,
            self.handle_line,
        )
        sys.monitoring.register_callback(
            tool_id,
            sys.monitoring.events.PY_RETURN,
            self.handle_return,
        )

    def reset_monitoring(self) -> None:
        # Reset the monitoring state
        self.__init__()

    def stop_monitoring(self) -> None:
        sys.monitoring.set_events(TOOL_ID, 0)
        sys.monitoring.free_tool_id(TOOL_ID)
        sys.monitoring.register_callback(
            TOOL_ID,
            sys.monitoring.events.PY_START,
            lambda *_: None,
        )
        sys.monitoring.register_callback(
            TOOL_ID,
            sys.monitoring.events.LINE,
            lambda *_: None,
        )
        sys.monitoring.register_callback(
            TOOL_ID,
            sys.monitoring.events.PY_RETURN,
            lambda *_: None,
        )


def instrument_code_recursive(code: CodeType) -> None:
    """Activate monitoring for the code and all nested code objects"""
    sys.monitoring.set_local_events(TOOL_ID, code, EVENTS)
    for const in code.co_consts:
        if isinstance(const, CodeType):
            instrument_code_recursive(const)
