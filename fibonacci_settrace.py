# https://explog.in/notes/settrace.html

import random
import time


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

import opcode  


# Global variable to track the last timestamp
last_time = None

def show_trace(frame, event, arg):
    global last_time
    current_time = time.time()
    
    frame.f_trace_opcodes = True
    code = frame.f_code
    offset = frame.f_lasti
    
    # Get the source code of the current file
    source_lines = None
    try:
        with open(code.co_filename, 'r') as f:
            source_lines = f.readlines()
    except:
        source_line = "<source not available>"
    
    # Get the current line of code being executed
    if source_lines and 0 <= frame.f_lineno-1 < len(source_lines):
        source_line = source_lines[frame.f_lineno-1].strip()
    else:
        source_line = "<line not available>"
    
    # Calculate time spent since last event
    elapsed_time = 0
    if last_time is not None:
        elapsed_time = (current_time - last_time) * 1000  # Convert to milliseconds
    
    # Update last_time for next calculation
    last_time = current_time
    
    print(f"| {event:10} | {str(arg):>4} |", end=' ')
    print(f"{frame.f_lineno:>4} | {frame.f_lasti:>6} |", end=' ')
    print(f"{opcode.opname[code.co_code[offset]]:<18} | {str(frame.f_locals):<35} | {elapsed_time:8.3f}ms | {source_line}")
    return show_trace


import sys

header = f"| {'event':10} | {'arg':>4} | line | offset | {'opcode':^18} | {'locals':^35} |"
print(header)
sys.settrace(show_trace)
fib(3)
# other_function()
sys.settrace(None)

# import inspect

# code = fib.__code__
# print(f"{'field':<20} | value")
# for name, val in inspect.getmembers(code):
#     if name.startswith("co_"):
#         print(f"{name:<20} | {val}")