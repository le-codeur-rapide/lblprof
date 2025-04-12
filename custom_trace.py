import opcode
import random
import sys
import time

# Track info for previous line
previous_line_info = None
last_time = None

def show_trace(frame, event, arg):
    global last_time, previous_line_info
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
    
    # Create current line info
    current_info = {
        'event': event,
        'arg': arg,
        'line_no': line_no,
        'offset': offset,
        'opcode': opcode.opname[code.co_code[offset]],
        'locals': frame.f_locals.copy(),
        'source': source_line
    }
    
    # If we have previous line info, print it with the time elapsed since then
    if previous_line_info and last_time:
        elapsed_time = (current_time - last_time) * 1000  # Convert to milliseconds
        prev = previous_line_info
        
        print(f"| {prev['event']:10} | {str(prev['arg']):>4} |", end=' ')
        print(f"{prev['line_no']:>4} | {prev['offset']:>6} |", end=' ')
        print(f"{prev['opcode']:<18} | {str(prev['locals']):<35} | {elapsed_time:8.3f}ms | {prev['source']}")
    
    # Store current info as previous for next iteration
    previous_line_info = current_info
    last_time = current_time
    
    return show_trace

def set_custom_trace():
    # Initialize the timer and start tracing
    global last_time
    last_time = time.time()
    sys.settrace(show_trace)