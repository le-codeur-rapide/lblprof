import csv
import logging
import sys
import time
from types import CodeType
from typing import NamedTuple

from lblprof.line_stat_object import LineKey


TOOL_ID = sys.monitoring.PROFILER_ID
PROFILER_NAME = "lblprof-monitor"
EVENTS = (
    sys.monitoring.events.LINE
    | sys.monitoring.events.PY_RETURN
    | sys.monitoring.events.PY_START
)


class LineEvent(NamedTuple):
    id: int
    file_name: str
    func_name: str
    line_no: int
    start_time: float
    stack_trace: list[LineKey]


class CodeMonitor:
    """Time and record sys.monitoring events"""

    def __init__(self):
        self.stack: list[LineKey] = list()
        self.events: list[LineEvent] = list()
        self.nb_events_recorded: int = 0

    def handle_call(self, code: CodeType, instruction_offset: int):
        """Code to execute when a function is called"""
        logging.debug(f"CALL in {code.co_name} at offset {instruction_offset}")
        self.stack.append(
            LineKey(
                file_name=code.co_filename,
                function_name=code.co_name,
                line_no=code.co_firstlineno,
            )
        )

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
                stack_trace=self.stack,
                start_time=start,
            )
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
                line_no=instruction_offset,
                stack_trace=self.stack,
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

    def stop_monitoring(self):
        sys.monitoring.free_tool_id(TOOL_ID)
        save_events_csv(self.events)


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
                        for lk in ev.stack_trace
                    ),
                ]
            )
