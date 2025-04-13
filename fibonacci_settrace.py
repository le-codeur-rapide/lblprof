# https://explog.in/notes/settrace.html

import random
import sys
import time

from custom_trace import  set_custom_trace, show_interactive_tree, show_tree, stop_custom_trace


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
        total += i ** 0.5
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
    from other_module import some_function
    time.sleep(1)  # Simulate some delay
def main():
    fib(2)
    # time.sleep(1)  # Simulate some delay
    # function_2_second()
    # # other_function()
    # function_using_json()

    # function_that_imports()
def main2():
    time.sleep(1)  # Simulate some delay


set_custom_trace()

main()
# main2()
time.sleep(1)  # Simulate some delay
fib(2)
stop_custom_trace()

# show_tree()
show_interactive_tree()

# build_tree()

# import inspect

# code = fib.__code__
# print(f"{'field':<20} | value")
# for name, val in inspect.getmembers(code):
#     if name.startswith("co_"):
#         print(f"{name:<20} | {val}")