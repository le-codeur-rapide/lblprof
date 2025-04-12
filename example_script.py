import os
import time
import random
import sys
import tracemalloc
import threading

prev_time = time.time()
tracemalloc.start()

# Get the full path of the current file for filtering
current_file = os.path.abspath(__file__)

def trace_func(frame, event, arg):
    global prev_time
    
    # Only trace this specific file
    filename = frame.f_code.co_filename
    # if filename != current_file:
    #     return trace_func  # Return the trace function to keep tracing
        
        
    if event == "line" or True:
        # Calculate time since last line
        curr_time = time.time()
        elapsed = curr_time - prev_time
        prev_time = curr_time
        
        # Get memory usage
        current, peak = tracemalloc.get_traced_memory()
        
        # Get the line of code being executed
        with open(filename, 'r') as f:
            lines = f.readlines()
            line_content = lines[frame.f_lineno - 1].strip()
        
        # Print detailed information
        print(f"Line {frame.f_lineno:3d} | Time: {elapsed:.6f}s | Mem: {current / 1024:.1f} KB | Code: {line_content}")
    
    return trace_func



if __name__ == "__main__":
    # Start tracing before any code executes
    sys.settrace(trace_func)
    threading.settrace(trace_func)

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
