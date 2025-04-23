# https://explog.in/notes/settrace.html

import random
import time
import logging

from lblprof import (
    set_custom_trace,
    show_interactive_tree,
    stop_custom_trace,
)

logging.basicConfig(level=logging.INFO)


def fib(n):
    i, f1, f2 = 1, 1, 1
    while i < n:
        f1, f2 = f2, f1 + f2
        i += 1
    time.sleep(1)  # Simulate some delay
    return f1


def other_function():
    print("Start processing...")

    print("Generating large list...")
    big_list = [random.random() for _ in range(10**3)]
    print(f"Generated list of {len(big_list)} elements")

    # 🐢 Slow part
    print("Simulating slow operation...")
    time.sleep(2)  # Simulate I/O delay

    print("Starting slow computation...")
    total = 0
    for i in range(10**3):
        total += i**0.5
    print(f"Computation result: {total}")

    print("Done.")


def quick_sub_function():
    print("This is a quick sub-function.")
    a = 1
    return a


def function_using_json():
    import json

    data = {"key": "value"}
    json_str = json.dumps(data)
    quick_sub_function()
    print(json_str)


def sub_function_1_second():
    time.sleep(1)  # Simulate some delay
    print("This sub-function sleeps for 1 second.")


def function_2_second():
    sub_function_1_second()
    time.sleep(1)  # Simulate some delay
    print("This function sleeps for 1 second.")


def function_that_imports():

    time.sleep(1)  # Simulate some delay


def main():
    fib(2)
    # fib(3)
    # time.sleep(1)  # Simulate some delay
    # function_2_second()
    # # other_function()
    # function_using_json()

    # function_that_imports()


def main2():
    time.sleep(1)  # Simulate some delay


# tracer = CodeMonitor()
# tracer.start_tracing()
set_custom_trace()

main()
main2()
time.sleep(1)  # Simulate some delay
# start = time.time()

# print(time.time() - start)
# time.sleep(2)
stop_custom_trace()
# show_tree()
# tracer.stop_tracing()

# tracer.tree.display_tree()
show_interactive_tree()

# build_tree()

# import inspect

# code = fib.__code__
# print(f"{'field':<20} | value")
# for name, val in inspect.getmembers(code):
#     if name.startswith("co_"):
#         print(f"{name:<20} | {val}")


# def is_user_code(frame):
#     module = inspect.getmodule(frame)
#     print(module)
#     if module is None:
#         return False

#     # Get the full path of the module
#     filename = inspect.getfile(module)
#     print(filename)

#     # Check if it's within the project directory
#     project_dir = os.getcwd()  # Assumes current working directory is project root

#     # Check if file is in project directory but not in site-packages
#     return (
#         project_dir in filename
#         and "site-packages" not in filename
#         and "dist-packages" not in filename
#     )


# print(is_user_code(inspect.currentframe()))
