import numpy as np  # noqa: F401
from lblprof.runtime_monitoring import start_profiling, stop_profiling
from zzz2 import f3  # noqa: F401
import logging

logging.basicConfig(level=logging.DEBUG)

print("Starting profiling...")
start_profiling()
print("Profiling started.")

# from lblprof.curses_ui import NodeTerminalUI  # noqa: F401
from zzdict import zzz_submodule  # noqa: F401


def f1():
    f3()
    return np.arange(10)


print("alalalallalaalalla")


def f2():
    f1()


f2()


stop_profiling()
