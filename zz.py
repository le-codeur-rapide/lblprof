import numpy as np  # noqa: F401
from finegrained_sysmon import instrument_start
from zzz2 import f3  # noqa: F401
# from lblprof.curses_ui import NodeTerminalUI  # noqa: F401


instrument_start()


def f1():
    f3()
    return np.arange(10)


print("alalalallalaalalla")


def f2():
    f1()


f2()
