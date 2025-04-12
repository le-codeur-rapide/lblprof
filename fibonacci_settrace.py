# https://explog.in/notes/settrace.html

import random
import sys
import time

from custom_trace import set_custom_trace


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
    big_list = [random.random() for _ in range(10**6)]
    print(f"Generated list of {len(big_list)} elements")

    # 🐢 Slow part
    print("Simulating slow operation...")
    time.sleep(2)  # Simulate I/O delay

    print("Starting slow computation...")
    total = 0
    for i in range(10**5):
        total += i ** 0.5
    print(f"Computation result: {total}")

    print("Done.")


header = f"| {'event':10} | {'arg':>4} | line | offset | {'opcode':^18} | {'locals':^35} |"
print(header)
set_custom_trace()
fib(3)
# other_function()

sys.settrace(None)  # Stop tracing


# import inspect

# code = fib.__code__
# print(f"{'field':<20} | value")
# for name, val in inspect.getmembers(code):
#     if name.startswith("co_"):
#         print(f"{name:<20} | {val}")