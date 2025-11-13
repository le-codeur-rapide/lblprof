import os
from pathlib import Path
import numpy as np  # noqa: F401
from zzz2 import f3  # noqa: F401


def instrument_start():
    if os.environ.get("LBLPROF_FINEGRAINED") == "1":
        print("Starting fine-grained monitoring...")
        return
    os.environ["LBLPROF_FINEGRAINED"] = "1"
    root_path = Path(__file__).parent.parent.resolve()
    entrypoint = Path(__file__).resolve()
    from finegrained_sysmon import main

    main(str(root_path), str(entrypoint))


instrument_start()

from lblprof.curses_ui import NodeTerminalUI  # noqa: F401

def f1():
    f3()
    return np.arange(10)


print("alalalallalaalalla")


def f2():
    f1()


f2()
