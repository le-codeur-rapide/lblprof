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
    print(f"CALL to {code.co_name} at offset {instruction_offset}")


def handle_start(code: CodeType, instruction_offset: int):
    print(f"START in {code.co_name} at offset {instruction_offset}")


def handle_line(code: CodeType, instruction_offset: int):
    print(f"LINE in {code.co_name}, at offset {instruction_offset}")


def handle_return(code: CodeType, instruction_offset: int, retval: object):
    print(f"RETURN from {code.co_name} at offset {instruction_offset}")


def register_hooks(tool_id: int = TOOL_ID):
    # register tool callbacks if not already registered
    if not sys.monitoring.get_tool(TOOL_ID):
        sys.monitoring.use_tool_id(TOOL_ID, PROFILER_NAME)
    # optional: register handlers (uncomment if needed)
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_START, handle_start
    )
    sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.LINE, handle_line)
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_RETURN, handle_return
    )


def instrument_code_recursive(code: CodeType):
    print(f"Instrumenting code object: {code.co_name}")

    sys.monitoring.set_local_events(TOOL_ID, code, EVENTS)
    for const in code.co_consts:
        # print(const)
        if isinstance(const, CodeType):
            instrument_code_recursive(const)
