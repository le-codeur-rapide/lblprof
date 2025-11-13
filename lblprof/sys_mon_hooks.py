import sys
from types import CodeType


TOOL_ID = sys.monitoring.PROFILER_ID
PROFILER_NAME = "lblprof-monitor"
EVENTS = (
    sys.monitoring.events.LINE
    | sys.monitoring.events.PY_RETURN
    | sys.monitoring.events.PY_START
)


def handle_call(code: CodeType, instruction_offset: int):
    """Code to execute when a function is called"""
    print(f"CALL in {code.co_name} at offset {instruction_offset}")


def handle_line(code: CodeType, instruction_offset: int):
    """Code to run when a line of code is executed"""
    print(f"LINE in {code.co_name}, at offset {instruction_offset}")


def handle_return(code: CodeType, instruction_offset: int, retval: object):
    """Code to run when a function is returned"""
    print(f"RETURN from {code.co_name} at offset {instruction_offset}")


def register_hooks(tool_id: int = TOOL_ID):
    """Create sys monitoring tool and add the different handlers"""
    # register tool callbacks if not already registered
    if not sys.monitoring.get_tool(tool_id):
        sys.monitoring.use_tool_id(tool_id, PROFILER_NAME)
    sys.monitoring.register_callback(
        tool_id, sys.monitoring.events.PY_START, handle_call
    )
    sys.monitoring.register_callback(tool_id, sys.monitoring.events.LINE, handle_line)
    sys.monitoring.register_callback(
        tool_id, sys.monitoring.events.PY_RETURN, handle_return
    )


def instrument_code_recursive(code: CodeType):
    """Activate monitoring for the code and all nested code objects"""
    sys.monitoring.set_local_events(TOOL_ID, code, EVENTS)
    for const in code.co_consts:
        if isinstance(const, CodeType):
            instrument_code_recursive(const)
