"""This module provides utilities to implement runtime monitoring"""

import importlib.abc
import importlib.machinery
import logging
from pathlib import Path
import sys
from types import ModuleType
from typing import Optional, Sequence

from lblprof.sys_monitoring import instrument_code_recursive

# Default dir to filter user code for instrumentation
DEFAULT_FILTER_DIRS = [
    Path.cwd().as_posix() + "/lblprof",
    Path.cwd().as_posix() + "/zzdict",
]


class InstrumentationFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self, name: str, path: Sequence[str] | None, target: Optional[ModuleType] = None
    ) -> Optional[importlib.machinery.ModuleSpec]:
        spec = importlib.machinery.PathFinder.find_spec(name, path, target)
        if not spec or not spec.origin or not spec.loader:
            return None
        if any(path in spec.origin for path in DEFAULT_FILTER_DIRS):
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
        code = instrument_file(file_path)
        exec(code, module.__dict__)
        return


def instrument_file(path: Path):
    """Returned instrumented code corresponding to a python file"""
    code = compile(path.read_text(), str(path), "exec")
    instrument_code_recursive(code)
    return code


def clear_cache_modules(filters: list[str]):
    """Clear sys.module with all modules corresponding to the filters"""
    for mod_name, mod in list(sys.modules.items()):
        if "zz" in mod_name:
            logging.debug(f"considering {mod_name}")
        # Built in modules
        mod_spec = getattr(mod, "__spec__", None)
        if mod_spec and mod_spec.origin:
            mod_path = Path(mod_spec.origin)
            if any(filter_dir in str(mod_path) for filter_dir in filters):
                logging.debug(f" removing {mod_name}")
                del sys.modules[mod_name]
