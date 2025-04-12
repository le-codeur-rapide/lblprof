import opcode
import sys
import time
import os
from collections import defaultdict

# Data structures to store trace information
function_start_times = {}
line_times = defaultdict(float)
line_hits = defaultdict(int)
line_source = {}
last_line_key = None
last_time = None

# Get user's home directory and site-packages paths to identify installed modules
HOME_DIR = os.path.expanduser('~')
SITE_PACKAGES_PATHS = [
    os.path.join(HOME_DIR, '.local/lib'),  # Local user packages
    '/usr/lib',                            # System-wide packages
    '/usr/local/lib',                      # Another common location
    'site-packages',                       # Catch any other site-packages
    'frozen importlib',                    # Frozen modules
]

def is_installed_module(filename):
    """Check if a file belongs to an installed module rather than user code."""
    return any(path in filename for path in SITE_PACKAGES_PATHS)

def custom_trace(frame, event, arg):
    global function_start_times, line_times, line_hits, line_source
    global last_line_key, last_time
    
    # Record time for this event
    now = time.time()
    
    # Set up function-level tracing
    frame.f_trace_opcodes = True
    code = frame.f_code
    func_name = code.co_name
    file_name = code.co_filename
    line_no = frame.f_lineno
    
    # Skip installed modules
    if is_installed_module(file_name):
        return None  # Don't trace into installed modules
    
    # Create a unique key for this line
    line_key = (file_name, func_name, line_no)
    
    # Store source line if we haven't seen it yet
    if line_key not in line_source:
        try:
            with open(file_name, 'r') as f:
                source_lines = f.readlines()
                line_source[line_key] = source_lines[line_no-1].strip() if 0 <= line_no-1 < len(source_lines) else "<line not available>"
        except:
            line_source[line_key] = "<source not available>"
    
    # Handle function start/end
    if event == 'call':
        function_start_times[(file_name, func_name)] = now
    elif event == 'line':
        # Count this line hit
        line_hits[line_key] += 1
        
        # If we have a previous line, record its time
        if last_line_key is not None and last_time is not None:
            elapsed = (now - last_time) * 1000
            line_times[last_line_key] += elapsed
        
        # Store current line for next calculation
        last_line_key = line_key
        last_time = now
    
    # When a function returns, calculate time for final line and print summary
    elif event == 'return':
        func_key = (file_name, func_name)
        if func_key in function_start_times:
            # Record time for the last line
            if last_line_key is not None and last_time is not None:
                elapsed = (now - last_time) * 1000
                line_times[last_line_key] += elapsed
            
            # Calculate total function time
            total_time = (now - function_start_times[func_key]) * 1000
            
            # Print function summary
            print(f"\n===== Function {func_key} completed in {total_time:.3f}ms =====")
            print(f"| {'Line':>4} | {'Hits':>6} | {'Time(ms)':>10} | {'Avg(ms)':>10} | {'%':>6} | Source")
            print('-' * 100)
            
            # Get all lines for this function
            func_lines = [(k, v) for k, v in line_times.items() if k[0] == file_name and k[1] == func_name]
            func_lines.sort(key=lambda x: x[0][2])  # Sort by line number
            
            # Print each line's stats
            for line_key, time_spent in func_lines:
                line_no = line_key[2]
                hits = line_hits[line_key]
                avg_time = time_spent / hits if hits > 0 else 0
                percent = (time_spent / total_time * 100) if total_time > 0 else 0
                
                print(f"| {line_no:>4} | {hits:>6} | {time_spent:>10.3f} | {avg_time:>10.3f} | {percent:>6.1f}% | {line_source[line_key]}")
            
            # Clean up
            del function_start_times[func_key]
    
    return custom_trace

def set_custom_trace():
    # Reset global state
    global function_start_times, line_times, line_hits, line_source
    global last_line_key, last_time
    
    function_start_times = {}
    line_times = defaultdict(float)
    line_hits = defaultdict(int)
    line_source = {}
    last_line_key = None
    last_time = None
    
    # Start tracing
    sys.settrace(custom_trace)