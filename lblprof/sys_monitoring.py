import csv
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

    def __init__(self):
        self.stack: list[LineKey] = list()
        """the stack is used to stock list of function calls that led to the
        current line"""
        self.events: list[LineEvent] = list()
        self.nb_events_recorded: int = 0
        self.tempo_line_infos: LineKey | None = None
        self.tree: LineStatsTree = LineStatsTree([])

    def handle_call(self, code: CodeType, instruction_offset: int):
        """Code to execute when a function is called"""
        logging.debug(f"CALL in {code.co_name} at offset {instruction_offset}")
        if not self.tempo_line_infos:
            # Here we are called by a root line, so no caller in the stack
            return
        caller_key = self.tempo_line_infos
        self.stack.append(caller_key)

    def handle_line(self, code: CodeType, instruction_offset: int):
        """Code to run when a line of code is executed"""
        logging.debug(f"LINE in {code.co_name}, at offset {instruction_offset}")
        start = time.perf_counter()
        self.events.append(
            LineEvent(
                id=self.nb_events_recorded,
                file_name=code.co_filename,
                func_name=code.co_name,
                line_no=instruction_offset,
                call_stack=self.stack.copy(),
                start_time=start,
            )
        )
        self.tempo_line_infos = LineKey(
            code.co_filename, code.co_name, instruction_offset
        )
        self.nb_events_recorded += 1

    def handle_return(self, code: CodeType, instruction_offset: int, retval: object):
        """Code to run when a function is returned"""
        logging.debug(f"RETURN from {code.co_name} at offset {instruction_offset}")
        start = time.perf_counter()
        self.events.append(
            LineEvent(
                id=self.nb_events_recorded,
                file_name=code.co_filename,
                func_name=code.co_name,
                line_no="END_OF_FRAME",
                call_stack=self.stack.copy(),
                start_time=start,
            )
        )
        if self.stack:
            self.stack.pop()

        self.nb_events_recorded += 1

    def register_hooks(self, tool_id: int = TOOL_ID):
        """Create sys monitoring tool and add the different handlers"""
        # register tool callbacks if not already registered
        if not sys.monitoring.get_tool(tool_id):
            sys.monitoring.use_tool_id(tool_id, PROFILER_NAME)
        sys.monitoring.register_callback(
            tool_id, sys.monitoring.events.PY_START, self.handle_call
        )
        sys.monitoring.register_callback(
            tool_id, sys.monitoring.events.LINE, self.handle_line
        )
        sys.monitoring.register_callback(
            tool_id, sys.monitoring.events.PY_RETURN, self.handle_return
        )

    def reset_monitoring(self):
        self.__init__()

    def stop_monitoring(self):
        sys.monitoring.set_events(TOOL_ID, 0)
        sys.monitoring.free_tool_id(TOOL_ID)
        sys.monitoring.register_callback(
            TOOL_ID, sys.monitoring.events.PY_START, lambda *args: None
        )
        sys.monitoring.register_callback(
            TOOL_ID, sys.monitoring.events.LINE, lambda *args: None
        )
        sys.monitoring.register_callback(
            TOOL_ID, sys.monitoring.events.PY_RETURN, lambda *args: None
        )

    def build_tree(self):
        self.tree = LineStatsTree(self.events)
        self.tree.build_tree()


def instrument_code_recursive(code: CodeType):
    """Activate monitoring for the code and all nested code objects"""
    sys.monitoring.set_local_events(TOOL_ID, code, EVENTS)
    for const in code.co_consts:
        if isinstance(const, CodeType):
            instrument_code_recursive(const)


def save_events_csv(events: list[LineEvent], path: str = "events.csv"):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["id", "file_name", "func_name", "line_no", "start_time", "stack_trace"]
        )

        for ev in events:
            writer.writerow(
                [
                    ev.id,
                    ev.file_name,
                    ev.func_name,
                    ev.line_no,
                    ev.start_time,
                    ";".join(
                        f"{lk.file_name}:{lk.function_name}:{lk.line_no}"
                        for lk in ev.call_stack
                    ),
                ]
            )
