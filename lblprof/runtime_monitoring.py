"""This module provides utilities to implement runtime monitoring"""

import importlib.abc
import importlib.machinery
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from types import CodeType, ModuleType

from lblprof.sys_monitoring import instrument_code_recursive

DEFAULT_FILTERS_INCLUDE = [os.getcwd()]
"""Path filters of code to include in analyzed code, default current working dir"""

DEFAULT_FILTERS_EXCLUDE = [
    d
    for d in os.listdir(".")
    if os.path.isdir(d) and (d.startswith(".") or d.startswith("venv"))
]
"""Paths that would have been included but are excluded.
Default to venv* and .* folders"""


def should_be_instrumented(
    code_path: str,
    include_filters: list[str] = DEFAULT_FILTERS_INCLUDE,
    exclude_filters: list[str] = DEFAULT_FILTERS_EXCLUDE,
) -> bool:
    """Return True if the code should be instrumented"""
    include = any(inc in code_path for inc in include_filters)
    exclude = any(exc in code_path for exc in exclude_filters)
    return include and not exclude


class InstrumentationFinder(importlib.abc.MetaPathFinder):
    """
    Finder of importlib that will change the loader of the found module if it
    correspond to filters.
    If None is returned, the next finder in sys.meta_path will be used
    """

    def find_spec(
        self,
        name: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        """
        This method is called by importlib to find a module.
        If the module correspond to filters, it will change the loader to
        InstrumentLoader, else it will return None and next finder in sys.meta_path
        will be used
        """
        spec = importlib.machinery.PathFinder.find_spec(name, path, target)
        if not spec or not spec.origin or not spec.loader:
            return None
        if should_be_instrumented(spec.origin):
            spec.loader = InstrumentLoader(spec.loader)
            return spec
        return None


class InstrumentLoader(importlib.abc.Loader):
    def __init__(self, loader: importlib.abc.Loader) -> None:
        # store the original loader
        self.loader = loader

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        # delegate module creation to the original loader
        return self.loader.create_module(spec)

    def exec_module(self, module: ModuleType) -> None:
        module_spec = module.__spec__
        if not module_spec or not module_spec.origin:
            return
        file_path = Path(module_spec.origin)
        code = instrument_file(file_path)
        exec(code, module.__dict__)
        return


def instrument_file(path: Path) -> CodeType:
    """Returned instrumented code corresponding to a python file"""
    code = compile(path.read_text(), str(path), "exec")
    instrument_code_recursive(code)
    return code


def clear_cache_modules() -> None:
    """Clear sys.module with all modules corresponding to the filters"""
    for mod_name, mod in list(sys.modules.items()):
        # Built in modules
        mod_spec = getattr(mod, "__spec__", None)
        if mod_spec and mod_spec.origin:
            path = str(Path(mod_spec.origin))

            if should_be_instrumented(path):
                logging.debug(f" removing {mod_name}")
                del sys.modules[mod_name]
