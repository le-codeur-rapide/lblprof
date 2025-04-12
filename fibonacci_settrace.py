# https://explog.in/notes/settrace.html

def fib(n):
    i, f1, f2 = 1, 1, 1
    while i < n:
        f1, f2 = f2, f1 + f2
        i += 1
    return f1

import opcode  


def show_trace(frame, event, arg):
    frame.f_trace_opcodes = True
    code = frame.f_code
    offset = frame.f_lasti

    print(f"| {event:10} | {str(arg):>4} |", end=' ')
    print(f"{frame.f_lineno:>4} | {frame.f_lasti:>6} |", end=' ')
    print(f"{opcode.opname[code.co_code[offset]]:<18} | {str(frame.f_locals):<35} |")
    return show_trace

import sys

header = f"| {'event':10} | {'arg':>4} | line | offset | {'opcode':^18} | {'locals':^35} |"
print(header)
sys.settrace(show_trace)
fib(3)
sys.settrace(None)

# import inspect

# code = fib.__code__
# print(f"{'field':<20} | value")
# for name, val in inspect.getmembers(code):
#     if name.startswith("co_"):
#         print(f"{name:<20} | {val}")