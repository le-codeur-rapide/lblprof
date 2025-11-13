"""This module provides utilities to implement runtime monitoring"""

import importlib.abc
import importlib.machinery
import importlib.util
import inspect
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Optional, Sequence

from lblprof.sys_mon_hooks import instrument_code_recursive, register_hooks

ENV_VARIABLE_FLAG = "LBLPROF_FINEGRAINED"


def start_profiling():
    if os.environ.get(ENV_VARIABLE_FLAG) == "1":
        return
    os.environ[ENV_VARIABLE_FLAG] = "1"
    caller_file = get_caller_file_path()
    print(f"__file__ is {caller_file}")
    # by default assume project root is two levels up from caller file
    root_path = Path(caller_file).parent.parent.resolve()
    entrypoint = Path(caller_file).resolve()

    register_hooks()
    sys.meta_path.insert(0, WrapFinder(root_path))

    # run entrypoint as __main__ (it will import modules on demand and they will be instrumented)
    spec = importlib.util.spec_from_file_location("__main__", entrypoint)
    assert spec and spec.loader
    spec.loader = InstrumentLoader(spec.loader)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(entrypoint)
    sys.modules["__main__"] = module
    spec.loader.exec_module(module)


def stop_profiling():
    pass


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


def instrument_file(path: Path):
    print(f"Instrumenting file: {path}")
    code = compile(path.read_text(), str(path), "exec")
    instrument_code_recursive(code)
    return code


def get_caller_file_path() -> Path:
    """Get the file path of the caller of the function that called this function."""
    # [2] because [0] is this function, [1] is the function that called this, and [2] is its caller
    caller_info = inspect.stack()[2]
    caller_file = Path(caller_info.filename).resolve()
    return caller_file


__all__ = ["start_profiling", "stop_profiling"]
