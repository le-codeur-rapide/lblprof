import opcode
import sys
import time
import os
from collections import defaultdict


class CodeTracer:
    def __init__(self):
        # Data structures to store trace information
        self.function_start_times = {}
        self.line_times = defaultdict(float)
        self.line_hits = defaultdict(int)
        self.line_source = {}
        self.call_stack = []  # Keep track of function call stack
        self.last_line_key = None
        self.last_time = None
        self.function_call_times = defaultdict(float)  # Track time spent in function calls
        self.function_line_stats = {}  # Store stats for each function's lines
        
        # Get user's home directory and site-packages paths to identify installed modules
        self.home_dir = os.path.expanduser('~')
        self.site_packages_paths = [
            os.path.join(self.home_dir, '.local/lib'),  # Local user packages
            '/usr/lib',                                # System-wide packages
            '/usr/local/lib',                          # Another common location
            'site-packages',                           # Catch any other site-packages
            'frozen importlib',                        # Frozen modules
            'frozen zipimport',                        # Frozen zipimport modules
            '<'                                        # built-in modules
        ]
    
    def is_installed_module(self, filename):
        """Check if a file belongs to an installed module rather than user code."""
        return any(path in filename for path in self.site_packages_paths)
    
    def trace_function(self, frame, event, arg):
        # Set up function-level tracing
        frame.f_trace_opcodes = True
        code = frame.f_code
        func_name = code.co_name
        file_name = code.co_filename
        line_no = frame.f_lineno
        
        # Skip installed modules
        if self.is_installed_module(file_name):
            return None  # Don't trace into installed modules
        
        # Record time for this event
        now = time.time()
        
        # Create a unique key for this line
        line_key = (file_name, func_name, line_no)
        func_key = (file_name, func_name)
        
        # Store source line if we haven't seen it yet
        if line_key not in self.line_source:
            try:
                with open(file_name, 'r') as f:
                    source_lines = f.readlines()
                    self.line_source[line_key] = source_lines[line_no-1].strip() if 0 <= line_no-1 < len(source_lines) else "<line not available>"
            except:
                self.line_source[line_key] = "<source not available>"
        
        # Handle function start/end
        if event == 'call':
            # We use the call stack to keep track of which function called which
            # sub function. This lets us attribute time correctly to the calling function.
            if self.last_line_key:
                self.call_stack.append(self.last_line_key)
            self.function_start_times[func_key] = now
        
        elif event == 'line':
            # Count this line hit
            self.line_hits[line_key] += 1
            
            # If we have a previous line, record its time
            if self.last_line_key is not None and self.last_time is not None:
                elapsed = (now - self.last_time) * 1000
                self.line_times[self.last_line_key] += elapsed
            
            # Store current line for next calculation
            self.last_line_key = line_key
            self.last_time = now
        
        # When a function returns, calculate time for final line and collect stats
        elif event == 'return':
            if func_key in self.function_start_times:
                # Record time for the last line
                if self.last_line_key is not None and self.last_time is not None:
                    elapsed = (now - self.last_time) * 1000
                    self.line_times[self.last_line_key] += elapsed
                
                # Calculate total function time
                total_time = (now - self.function_start_times[func_key]) * 1000
                
                # Record this function's time for attribution to parent functions
                self.function_call_times[func_key] = total_time
                
                # If there's a parent function, attribute this time to the line that called us
                if self.call_stack:
                    parent_call_line = self.call_stack.pop()
                    self.line_times[parent_call_line] += total_time
                
                # Skip very short functions to reduce noise
                if total_time < 10:
                    return self.trace_function
                
                # Collect line stats for this function
                func_lines = [(k, v) for k, v in self.line_times.items() if k[0] == file_name and k[1] == func_name]
                func_lines.sort(key=lambda x: x[0][2])  # Sort by line number
                
                # Calculate measured total for better percentages
                measured_total = sum(time_spent for _, time_spent in func_lines)
                
                # Build line stats for this function
                line_stats = []
                for line_key, time_spent in func_lines:
                    line_no = line_key[2]
                    hits = self.line_hits[line_key]
                    avg_time = time_spent / hits if hits > 0 else 0
                    percent = (time_spent / measured_total * 100) if measured_total > 0 else 0
                    
                    line_stats.append({
                        'line_no': line_no,
                        'hits': hits,
                        'time': time_spent,
                        'avg_time': avg_time,
                        'percent': percent,
                        'source': self.line_source[line_key]
                    })
                
                # Store the function stats
                self.function_line_stats[func_key] = {
                    'total_time': total_time,
                    'lines': line_stats
                }
                
                # Clean up
                del self.function_start_times[func_key]
        
        return self.trace_function
    
    def start_tracing(self):
        # Reset state
        self.__init__()
        # Start tracing
        sys.settrace(self.trace_function)
    
    def stop_tracing(self):
        sys.settrace(None)
    
    def get_function_summary(self):
        """Return the function execution time summary as a dictionary."""
        if not self.function_call_times:
            return {"error": "No functions were profiled."}
        
        # Calculate total program time
        total_program_time = sum(self.function_call_times.values())
        
        # Sort functions by time (descending)
        sorted_functions = sorted(self.function_call_times.items(), key=lambda x: x[1], reverse=True)
        
        # Build function summary
        function_summary = []
        for func_key, time_spent in sorted_functions:
            func_name = func_key[1]
            percent = (time_spent / total_program_time * 100) if total_program_time > 0 else 0
            
            function_summary.append({
                'function_name': func_name,
                'file_name': func_key[0],
                'time_ms': time_spent,
                'percent': percent
            })
        
        return {
            'total_time_ms': total_program_time,
            'functions': function_summary
        }
    
    def get_function_line_stats(self, func_key):
        """Return the line statistics for a specific function."""
        if func_key not in self.function_line_stats:
            return {"error": f"Function {func_key} was not profiled or had very short execution time."}
        
        return self.function_line_stats[func_key]
    
    def get_all_line_stats(self):
        """Return line statistics for all functions."""
        return self.function_line_stats
    
    # Display methods - these turn the data into formatted output
    def print_function_summary(self):
        """Print a summary of all function execution times."""
        summary = self.get_function_summary()
        
        if "error" in summary:
            print(summary["error"])
            return
        
        total_program_time = summary['total_time_ms']
        function_summary = summary['functions']
        
        print("\n\n============================================================")
        print("FUNCTION EXECUTION TIME SUMMARY")
        print("============================================================")
        print(f"| {'Function':^40} | {'Time(ms)':>10} | {'%':>6} |")
        print('-' * 65)
        
        for func in function_summary:
            print(f"| {func['function_name']:40} | {func['time_ms']:>10.3f} | {func['percent']:>6.1f}% |")
        
        print('-' * 65)
        print(f"| {'TOTAL':40} | {total_program_time:>10.3f} | 100.0% |")
        print("============================================================")
    
    def print_function_line_stats(self, func_key):
        """Print detailed line statistics for a specific function."""
        stats = self.get_function_line_stats(func_key)
        
        if "error" in stats:
            print(stats["error"])
            return
        
        print(f"\n===== Function {func_key} completed in {stats['total_time']:.3f}ms =====")
        print(f"| {'Line':>4} | {'Hits':>6} | {'Time(ms)':>10} | {'Avg(ms)':>10} | {'%':>6} | Source")
        print('-' * 100)
        
        for line in stats['lines']:
            print(f"| {line['line_no']:>4} | {line['hits']:>6} | {line['time']:>10.3f} | " +
                  f"{line['avg_time']:>10.3f} | {line['percent']:>6.1f}% | {line['source']}")
    
    def print_all_line_stats(self):
        """Print detailed line statistics for all profiled functions."""
        for func_key in self.function_line_stats:
            self.print_function_line_stats(func_key)
            print()  # Add a blank line between functions


# Create a singleton instance for the module
tracer = CodeTracer()

def set_custom_trace():
    tracer.start_tracing()

def stop_custom_trace():
    tracer.stop_tracing()

def print_summary():
    tracer.print_function_summary()

def print_all_details():
    tracer.print_all_line_stats()