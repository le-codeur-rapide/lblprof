import time
import numpy as np  # noqa: F401
from lblprof.runtime_monitoring import start_profiling, stop_profiling, display_tui
import logging
from zzz2 import f3  # noqa: F401

logging.basicConfig(level=logging.DEBUG)

print("Starting profiling...")
start_profiling()
print("Profiling started.")

# from lblprof.curses_ui import NodeTerminalUI  # noqa: F401
from zzdict.zzz_submodule import f4


def f1():
    f3()
    return np.arange(10)


print("alalalallalaalalla")


def f2():
    time.sleep(0.1)
    f1()
    f4()


f2()


stop_profiling()
display_tui()
