import importlib.machinery
from pathlib import Path
import sys
from types import CodeType, ModuleType
import importlib.abc
import importlib.util
from typing import Optional, Sequence

TOOL_ID = sys.monitoring.PROFILER_ID
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


def instrument_code_recursive(code: CodeType):
    print(f"Instrumenting code object: {code.co_name}")

    sys.monitoring.set_local_events(TOOL_ID, code, EVENTS)
    for const in code.co_consts:
        # print(const)
        if isinstance(const, CodeType):
            instrument_code_recursive(const)


def instrument_file(path: Path):
    print(f"Instrumenting file: {path}")
    code = compile(path.read_text(), str(path), "exec")
    instrument_code_recursive(code)
    return code


class InstrumentLoader(importlib.abc.Loader):
    def __init__(self, loader: importlib.abc.Loader):
        # store the original loader
        self.loader = loader

    def create_module(self, spec: importlib.machinery.ModuleSpec):
        # delegate module creation to the original loader
        return self.loader.create_module(spec)

    def exec_module(self, module: ModuleType) -> None:
        print(f"module is {module.__dict__}")
        module_spec = module.__spec__
        if not module_spec:
            return
        file_path = module_spec.origin
        if not file_path:
            return
        file_path = Path(file_path)
        if file_path and "lblprof" in file_path.parts and "/lib" not in str(file_path):
            code = instrument_file(file_path)
            exec(code, module.__dict__)
            return
        return


class WrapFinder(importlib.abc.MetaPathFinder):
    def __init__(self, root: Path):
        self.root = root.resolve()

    def find_spec(
        self, name: str, path: Sequence[str] | None, target: Optional[ModuleType] = None
    ) -> Optional[importlib.machinery.ModuleSpec]:
        spec = importlib.machinery.PathFinder.find_spec(name, path, target)
        if not spec or not spec.origin or not spec.loader:
            return None
        if "/lib" not in spec.origin:
            print(f"WrapFinder: found spec {spec} for module {name}")
            spec.loader = InstrumentLoader(spec.loader)
            return spec
        return None


def main(root_path: str, entrypoint_path: str):
    root = Path(root_path).resolve()
    entrypoint = Path(entrypoint_path).resolve()

    # register tool callbacks if not already registered
    if not sys.monitoring.get_tool(TOOL_ID):
        sys.monitoring.use_tool_id(TOOL_ID, "lblprof-monitor")
    # optional: register handlers (uncomment if needed)
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_START, handle_start
    )
    sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.LINE, handle_line)
    sys.monitoring.register_callback(
        TOOL_ID, sys.monitoring.events.PY_RETURN, handle_return
    )

    # insert finder that only looks inside project root
    sys.meta_path.insert(0, WrapFinder(root))
    # print(sys.meta_path)
    path_finder = sys.meta_path[4]
    print(f"Using path finder: {path_finder.__dict__}")
    # run entrypoint as __main__ (it will import modules on demand and they will be instrumented)
    spec = importlib.util.spec_from_file_location("__main__", entrypoint)
    assert spec and spec.loader
    spec.loader = InstrumentLoader(spec.loader)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(entrypoint)
    sys.modules["__main__"] = module
    spec.loader.exec_module(module)


if __name__ == "__main__":
    # usage: python this_script.py /path/to/project /path/to/entrypoint.py
    main(sys.argv[1], sys.argv[2])
