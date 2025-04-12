import opcode
import random
import sys
import time

line_times = {}
last_time = None
current_line = None

def show_trace(frame, event, arg):
    global last_time, current_line
    current_time = time.time()
    
    frame.f_trace_opcodes = True
    code = frame.f_code
    offset = frame.f_lasti
    line_no = frame.f_lineno
    
    # Get the source code of the current file
    source_lines = None
    try:
        with open(code.co_filename, 'r') as f:
            source_lines = f.readlines()
    except:
        source_line = "<source not available>"
    
    # Get the current line of code being executed
    if source_lines and 0 <= line_no-1 < len(source_lines):
        source_line = source_lines[line_no-1].strip()
    else:
        source_line = "<line not available>"
    
    # Calculate time spent since last event
    elapsed_time = 0
    if last_time is not None:
        elapsed_time = (current_time - last_time) * 1000  # Convert to milliseconds
        
        # Store time for the previous line
        if current_line is not None:
            print(f"Time spent on line {current_line}: {elapsed_time:.3f}ms")
            line_times[current_line] = elapsed_time
    
    # Get time for this line (if already recorded from a previous visit)
    # print(f"line_no: {line_no}")
    # print(f"line_times: {line_times}")
    displayed_time = line_times.get(line_no, 0)
    
    # Update for next calculation
    last_time = current_time
    current_line = line_no
    
    print(f"| {event:10} | {str(arg):>4} |", end=' ')
    print(f"{line_no:>4} | {frame.f_lasti:>6} |", end=' ')
    print(f"{opcode.opname[code.co_code[offset]]:<18} | {str(frame.f_locals):<35} | {displayed_time:8.3f}ms | {source_line}")
    return show_trace

def set_custom_trace():
    # Set the trace function
    sys.settrace(show_trace)
    