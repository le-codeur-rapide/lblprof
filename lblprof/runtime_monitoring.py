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
# Default dir to filter user code for instrumentation
DEFAULT_FILTER_DIRS = Path.cwd().as_posix() + "/lblprof"


def start_profiling():
    if os.environ.get(ENV_VARIABLE_FLAG) == "1":
        return
    os.environ[ENV_VARIABLE_FLAG] = "1"

    # 1. Register sys.monitoring hooks
    register_hooks()

    # 2. Find the *current* module (the one calling start_profiling)
    caller_frame = inspect.stack()[1]
    caller_code = caller_frame.frame.f_code
    instrument_code_recursive(caller_code)

    # 3. Install import hook to instrument future imports
    sys.meta_path.insert(0, WrapFinder())

    # 4. Remove already loaded modules that match the filter dirs so they can be re-imported and instrumented
    for mod_name, mod in list(sys.modules.items()):
        mod_spec = getattr(mod, "__spec__", None)
        if mod_spec and mod_spec.origin:
            mod_path = Path(mod_spec.origin)
            if any(
                filter_dir in str(mod_path)
                for filter_dir in DEFAULT_FILTER_DIRS.split(os.pathsep)
            ):
                del sys.modules[mod_name]


def stop_profiling():
    pass


class WrapFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self, name: str, path: Sequence[str] | None, target: Optional[ModuleType] = None
    ) -> Optional[importlib.machinery.ModuleSpec]:
        spec = importlib.machinery.PathFinder.find_spec(name, path, target)
        if not spec or not spec.origin or not spec.loader:
            return None
        if "/lib" not in spec.origin:
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
        else:
            print(f"Executing module {module.__name__} without instrumentation")
        return


def instrument_file(path: Path):
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
