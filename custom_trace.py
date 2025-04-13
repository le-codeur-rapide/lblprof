import sys
import time
import os
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any
from pydantic import BaseModel, Field
from pydantic import (
    field_validator, 
    ConfigDict
)
from pydantic import model_validator

# Define Pydantic models for our data structures
class LineStats(BaseModel):
    """Statistics for a single line of code."""
    model_config = ConfigDict(validate_assignment=True)
    
    line_no: int = Field(..., ge=1, description="Line number in the source file")
    hits: int = Field(..., ge=0, description="Number of times this line was executed")
    time: float = Field(..., ge=0, description="Time spent on this line in milliseconds")
    avg_time: float = Field(..., ge=0, description="Average time per hit in milliseconds")
    percent: float = Field(..., ge=0, le=100, description="Percentage of total time of the function spent on this line")
    source: str = Field(..., min_length=1, description="Source code for this line")
    
    @field_validator('avg_time', mode='after')
    @classmethod
    def validate_avg_time(cls, v, info):
        """Validate that average time is consistent with time and hits."""
        if 'time' in info.data and 'hits' in info.data and info.data['hits'] > 0:
            expected_avg = info.data['time'] / info.data['hits']
            if abs(v - expected_avg) > 0.001:  # Allow small floating point differences
                raise ValueError(f"avg_time ({v}) should equal time/hits ({expected_avg})")
        return v


class FunctionStats(BaseModel):
    """Statistics for a function execution."""
    model_config = ConfigDict(validate_assignment=True)
    
    function_key: Tuple[str, str] = Field(..., description="Key identifying the function (file_name, function_name)")
    total_time: float = Field(..., ge=0, description="Total time spent in this function in milliseconds")
    lines: List[LineStats] = Field(..., description="Statistics for each line in this function")

    @field_validator('lines')
    @classmethod
    def validate_min_items(cls, v):
        """Validate that there is at least one line."""
        if len(v) < 1:
            raise ValueError("At least one line statistic is required")
        return v
    
    @model_validator(mode='after')
    def validate_line_percentages(self) -> 'FunctionStats':
        """Validate that line percentages sum to approximately 100%.    
            And that the sum of line times is consistent with total_time."""
        if self.lines:
            total_percent = sum(line.percent for line in self.lines)
            # Allow small rounding errors (within 1%)
            if not (99.0 <= total_percent <= 101.0):
                raise ValueError(f"Line percentages sum to {total_percent}, expected approximately 100%")
            
            # Also validate that the sum of line times is consistent with total_time
            total_line_time = sum(line.time for line in self.lines)
            # Allow some discrepancy due to measurement limitations
            if total_line_time > 0 and abs(total_line_time - self.total_time) / total_line_time > 0.1:
                raise ValueError(f"Sum of line times ({total_line_time}ms) differs significantly from total time ({self.total_time}ms)")
        return self


class FunctionSummary(BaseModel):
    """Summary information for a single function."""
    model_config = ConfigDict(validate_assignment=True)
    
    function_name: str = Field(..., min_length=1)
    file_name: str = Field(..., min_length=1)
    time_ms: float = Field(..., ge=0)
    percent: float = Field(..., ge=0, le=100, description="Percentage of total time spent in this function")


class TraceSummary(BaseModel):
    """Overall summary of profiling results."""
    model_config = ConfigDict(validate_assignment=True)
    
    total_time_ms: float = Field(..., ge=0, description="Total time spent in all functions")
    functions: List[FunctionSummary] = Field(..., description="Summary of each function's execution")
    
    @model_validator(mode='after')
    def validate_function_percentages(self) -> 'TraceSummary':
        """Validate that function percentages sum to approximately 100%."""
        if self.functions:
            total_percent = sum(func.percent for func in self.functions)
            # Allow small rounding errors (within 1%)
            if not (99.0 <= total_percent <= 101.0):
                raise ValueError(f"Function percentages sum to {total_percent}, expected approximately 100%")
            
            # Also validate that the sum of function times equals total_time
            total_func_time = sum(func.time_ms for func in self.functions)
            if abs(total_func_time - self.total_time_ms) > 0.001:
                raise ValueError(f"Sum of function times ({total_func_time}ms) doesn't match total time ({self.total_time_ms}ms)")
        return self


class LineState:
    """Maintains state information for a code line."""
    def __init__(self, line_key: Tuple[str, str, int], timestamp: float):
        self.line_key = line_key
        self.timestamp = timestamp


class CodeTracer:
    def __init__(self):
        # Data structures to store trace information
        self.function_start_times: Dict[Tuple[str, str], float] = {}
        self.line_times: Dict[Tuple[str, str, int], float] = defaultdict(float)
        self.line_hits: Dict[Tuple[str, str, int], int] = defaultdict(int)
        self.line_source: Dict[Tuple[str, str, int], str] = {}
        self.call_stack: List[Tuple[str, str, int]] = []  # Keep track of function call stack
        
        # Stack of line states to handle nested function calls
        self.line_state_stack: List[LineState] = []
        self.last_line_key: Optional[Tuple[str, str, int]] = None
        self.last_time: Optional[float] = None
        
        self.function_call_times: Dict[Tuple[str, str], float] = defaultdict(float)  # Track time spent in function calls
        self.function_line_stats: Dict[Tuple[str, str], FunctionStats] = {}  # Store stats for each function's lines
        
        # Map of functions to their active line keys
        self.function_active_lines: Dict[Tuple[str, str], Tuple[str, str, int]] = {}
        
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
    
    def is_installed_module(self, filename: str) -> bool:
        """Check if a file belongs to an installed module rather than user code."""
        return any(path in filename for path in self.site_packages_paths) or len(filename) ==   0
    
    def trace_function(self, frame: Any, event: str, arg: Any) -> Any:
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
            except Exception:
                self.line_source[line_key] = "<source not available>"
        
        # Handle function start/end
        if event == 'call':
            # Push the current line state onto the stack before starting a new function
            if self.last_line_key is not None:
                self.line_state_stack.append(LineState(self.last_line_key, self.last_time))
                self.call_stack.append(self.last_line_key)
            
            # Record function start time
            self.function_start_times[func_key] = now
            
            # Reset line tracking for this function call
            self.last_line_key = None
            self.last_time = None
        
        elif event == 'line':
            # Count this line hit
            self.line_hits[line_key] += 1
            
            # If we have a previous line in this function, record its time
            if self.last_line_key is not None and self.last_time is not None:
                elapsed = (now - self.last_time) * 1000
                self.line_times[self.last_line_key] += elapsed
            
            # Update the function's current active line
            self.function_active_lines[func_key] = line_key
            
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
                
                # If there's a parent function that called us, attribute this time to that line
                if self.call_stack:
                    parent_call_line = self.call_stack.pop()
                    self.line_times[parent_call_line] += total_time
                
                # Pop the previous line state from the stack
                if self.line_state_stack:
                    prev_state = self.line_state_stack.pop()
                    self.last_line_key = prev_state.line_key
                    self.last_time = now  # Use current time, not the stored time
                else:
                    self.last_line_key = None
                    self.last_time = None
                
                # Skip very short functions to reduce noise
                if total_time < 10:
                    return self.trace_function
                
                # Collect line stats for this function
                func_lines = [(k, v) for k, v in self.line_times.items() if k[0] == file_name and k[1] == func_name]
                func_lines.sort(key=lambda x: x[0][2])  # Sort by line number
                
                if not func_lines:
                    # Skip functions with no line data
                    return self.trace_function
                
                # Calculate measured total for better percentages
                measured_total = sum(time_spent for _, time_spent in func_lines)
                
                # Build line stats for this function
                line_stats = []
                for line_key, time_spent in func_lines:
                    line_no = line_key[2]
                    hits = self.line_hits[line_key]
                    avg_time = time_spent / hits if hits > 0 else 0
                    percent = (time_spent / measured_total * 100) if measured_total > 0 else 0
                    
                    line_stats.append(LineStats(
                        line_no=line_no,
                        hits=hits,
                        time=time_spent,
                        avg_time=avg_time,
                        percent=percent,
                        source=self.line_source[line_key]
                    ))
                
                # Store the function stats
                self.function_line_stats[func_key] = FunctionStats(
                    function_key=func_key,
                    total_time=total_time,
                    lines=line_stats
                )
                
                # Clean up
                del self.function_start_times[func_key]
                if func_key in self.function_active_lines:
                    del self.function_active_lines[func_key]
        
        return self.trace_function
    
    def start_tracing(self) -> None:
        # Reset state
        self.__init__()
        # Start tracing
        sys.settrace(self.trace_function)
    
    def stop_tracing(self) -> None:
        sys.settrace(None)
    
    def get_function_summary(self) -> TraceSummary:
        """Return the function execution time summary as a Pydantic model."""
        if not self.function_call_times:
            raise ValueError("No function call times recorded.")
        
        # Calculate total program time
        total_program_time = sum(self.function_call_times.values())
        
        # Sort functions by time (descending)
        sorted_functions = sorted(self.function_call_times.items(), key=lambda x: x[1], reverse=True)
        
        # Build function summary
        function_summary = []
        for func_key, time_spent in sorted_functions:
            func_name = func_key[1]
            percent = (time_spent / total_program_time * 100) if total_program_time > 0 else 0
            
            function_summary.append(FunctionSummary(
                function_name=func_name,
                file_name=func_key[0],
                time_ms=time_spent,
                percent=percent
            ))
        
        return TraceSummary(
            total_time_ms=total_program_time,
            functions=function_summary
        )
    
    def get_function_line_stats(self, func_key: Tuple[str, str]) -> FunctionStats:
        """Return the line statistics for a specific function."""
        if func_key not in self.function_line_stats:
            raise ValueError(f"Function {func_key} not found in line stats.")
        
        return self.function_line_stats[func_key]
    
    def get_all_line_stats(self) -> Dict[Tuple[str, str], FunctionStats]:
        """Return line statistics for all functions."""
        return self.function_line_stats
    
    def print_function_summary(self, current_file: Optional[str] = None, n: Optional[int] = None) -> None:
        """Print a summary of function execution times.
        
        Args:
            current_file: Optional[str] - If provided, only shows functions from this file.
                                        If None, shows functions from all files.
            n: Optional[int] - If provided, only shows the top n longest-running functions.
                            If None, shows all functions.
        """
        try:
            summary = self.get_function_summary()
            
            total_program_time = summary.total_time_ms
            function_summary = summary.functions
            
            # Filter by file if requested
            if current_file:
                current_file = os.path.abspath(current_file)
                original_count = len(function_summary)
                function_summary = [
                    func for func in function_summary 
                    if os.path.abspath(func.file_name) == current_file
                ]
                filtered_count = len(function_summary)
                
                if filtered_count == 0:
                    print(f"No functions traced in file: {os.path.basename(current_file)}")
                    return
            
            # Sort by time (descending)
            function_summary.sort(key=lambda x: x.time_ms, reverse=True)
            
            # Limit to top n if specified
            if n is not None and len(function_summary) > n:
                function_summary = function_summary[:n]
            
            # Calculate actual displayed total time (not sum of all functions since that double-counts)
            # For file-specific display, we need to recalculate the percentage based on the file's contribution
            # rather than simply summing the individual function times
            if current_file:
                file_functions_time = sum(func.time_ms for func in function_summary)
                # This is the sum of the filtered functions, used only for display
                displayed_total_time = file_functions_time
            else:
                # When showing all functions, use the computed total program time
                displayed_total_time = total_program_time
            
            # Create title based on filtering
            title = "FUNCTION EXECUTION TIME SUMMARY"
            if current_file:
                title += f" FOR: {os.path.basename(current_file)}"
            if n is not None:
                title += f" (TOP {n})"
            
            # Print the summary
            print("\n\n============================================================")
            print(title)
            print("============================================================")
            print(f"| {'Function':^40} | {'Time(ms)':>10} | {'%':>6} |")
            print('-' * 65)
            
            for func in function_summary:
                if func.time_ms < 10:
                    continue
                    
                # Get just the filename without path
                filename = os.path.basename(func.file_name)
                func_name = f"{filename}::{func.function_name}"
                
                # If filtering by file, percentage is relative to file total
                if current_file:
                    file_percent = (func.time_ms / displayed_total_time * 100) if displayed_total_time > 0 else 0
                    print(f"| {func_name:40} | {func.time_ms:>10.3f} | {file_percent:>6.1f}% |")
                else:
                    # Otherwise use program percentage
                    print(f"| {func_name:40} | {func.time_ms:>10.3f} | {func.percent:>6.1f}% |")
            
            print('-' * 65)
            
            # Show displayed total - this is the key change
            print(f"| {'DISPLAYED TOTAL':40} | {displayed_total_time:>10.3f} | 100.0% |")
            
            # No longer showing program total when filtering as it causes confusion
            print("============================================================")
        except ValueError as e:
            print(f"Error: {e}")
    
    def print_function_line_stats(self, func_key: Tuple[str, str]) -> None:
        """Print detailed line statistics for a specific function."""
        stats = self.get_function_line_stats(func_key)
        
        print(f"\n===== Function {func_key} completed in {stats.total_time:.3f}ms =====")
        print(f"| {'Line':>4} | {'Hits':>6} | {'Time(ms)':>10} | {'Avg(ms)':>10} | {'%':>6} | Source")
        print('-' * 100)
        
        for line in stats.lines:
            print(f"| {line.line_no:>4} | {line.hits:>6} | {line.time:>10.3f} | " +
                  f"{line.avg_time:>10.3f} | {line.percent:>6.1f}% | {line.source}")
    
    def print_all_line_stats(self, n: Optional[int] = None) -> None:
        """Print detailed line statistics for profiled functions.
        
        Args:
            n: Optional[int] - If provided, only shows the top n longest-running functions.
                            If None, shows all functions.
        """
        # Get all function stats and sort by total time (descending)
        func_stats = [(func_key, stats) for func_key, stats in self.function_line_stats.items()]
        func_stats.sort(key=lambda x: x[1].total_time, reverse=False)
        
        # Limit to top n if specified
        if n is not None:
            func_stats = func_stats[-n:]
        
        # If no functions were profiled or n is 0, print a message
        if not func_stats:
            print("No function statistics available.")
            return
        
        # Print stats for each function
        for i, (func_key, _) in enumerate(func_stats):
            self.print_function_line_stats(func_key)
            # Add a blank line between functions, but not after the last one
            if i < len(func_stats) - 1:
                print()


# Create a singleton instance for the module
tracer = CodeTracer()

def set_custom_trace() -> None:
    global tracer
    tracer = CodeTracer()
    tracer.start_tracing()

def stop_custom_trace() -> None:
    tracer.stop_tracing()

def print_summary(n: Optional[int] = None) -> None:
    """Print a summary of function execution times.
    
    By default, only shows functions from the file where this function is called.
    
    Args:
        n: Optional[int] - If provided, only shows the top n longest-running functions.
    """
    # Get the current file path using inspection
    import inspect
    caller_frame = inspect.currentframe().f_back
    current_file = caller_frame.f_code.co_filename if caller_frame else None
    
    tracer.print_function_summary(current_file=current_file, n=n)

def print_all_details() -> None:
    tracer.print_all_line_stats(5)