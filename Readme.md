# LBLProf

LBLProf is simple a line by line terminal based time profiler. It allows you to track the duration of each line and get a tree of the execution of the code.

It comes with a simple interactive terminal UI to navigate the tree and see the stats of each line.
Example of the terminal ui:

![Example of the terminal ui](./docs/terminalui_showcase.png)

> [!WARNING]
> LBLProf is a tool that is based on the sys.monitoring API that is available in Python 3.12 and above.
> **It means that you need to use Python 3.12 or above to use it.**

# Documentation

## Installation

```bash
pip install lblprof
```

The only dependency of this package is pydantic, the rest is standard library.


## Usage

This package contains 4 main functions:
- `start_tracing()`: Start the tracing of the code.
- `stop_tracing()`: Stop the tracing of the code, build the tree and compute stats
- `show_interactive_tree(min_time_s: float = 0.1)`: show the interactive duration tree in the terminal.
- `show_tree()`: print the tree to console.

```python
from lblprof import start_tracing, stop_tracing, show_interactive_tree, show_tree

start_tracing()

# Your code here (Any code)

stop_tracing()
show_tree() # print the tree to console
show_interactive_tree() # show the interactive tree in the terminal
```

## How it works

LBLProf is based on the sys.monitoring API that is available in Python 3.12 and above. [PEP 669](https://peps.python.org/pep-0669/)

This new API allow us to cut down tracing when we are entering installed package and limit the tracing to the code of the user.

