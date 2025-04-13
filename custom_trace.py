import logging
logging.basicConfig(level=logging.DEBUG)
import sys
import time
import os
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional, Any
from pydantic import BaseModel, Field
from pydantic import (
    ConfigDict
)

class LineStats(BaseModel):
    """Statistics for a single line of code."""
    model_config = ConfigDict(validate_assignment=True)
    
    file_name: str = Field(..., min_length=1, description="File containing this line")
    function_name: str = Field(..., min_length=1, description="Function containing this line")
    line_no: int = Field(..., ge=1, description="Line number in the source file")
    hits: int = Field(..., ge=0, description="Number of times this line was executed")
    time: float = Field(..., ge=0, description="Time spent on this line in milliseconds")
    avg_time: float = Field(..., ge=0, description="Average time per hit in milliseconds")
    source: str = Field(..., min_length=1, description="Source code for this line")
    child_time: float = Field(default=0.0, ge=0, description="Time spent in called lines")
    
    # Parent line that called this function (optional for root/top-level lines)
    parent_key: Optional[Tuple[str, str, int]] = None
    
    # Children lines called by this line (populated during analysis)
    child_keys: List[Tuple[str, str, int]] = Field(default_factory=list)
    
    @property
    def key(self) -> Tuple[str, str, int]:
        """Get the unique key for this line."""
        return (self.file_name, self.function_name, self.line_no)
    
    @property
    def self_time(self) -> float:
        """Get time spent on this line excluding child calls."""
        return max(0.0, self.time - self.child_time)
    
    @property
    def total_time(self) -> float:
        """Get total time including child calls."""
        return self.time



class CodeTracer:
    def __init__(self):
        # Data structures to store trace information - everything is lines now
        self.line_times: Dict[Tuple[str, str, int], float] = defaultdict(float)
        self.line_hits: Dict[Tuple[str, str, int], int] = defaultdict(int)
        self.line_source: Dict[Tuple[str, str, int], str] = {}
        
        # Track parent-child relationships between lines
        self.line_parents: Dict[Tuple[str, str, int], Optional[Tuple[str, str, int]]] = {}
        self.line_children: Dict[Tuple[str, str, int], Set[Tuple[str, str, int]]] = defaultdict(set)
        
        # Track function entry points - we need this to determine caller-callee relationships
        self.function_entries: Dict[Tuple[str, str], Tuple[str, str, int]] = {}
        
        # Call stack to handle nested calls
        self.call_stack: List[Tuple[str, str, int]] = []
        
        # Current line tracking
        self.last_line_key: Optional[Tuple[str, str, int]] = None
        self.last_time: Optional[float] = None
        
        # Statistics for report generation
        self.total_time_ms: float = 0
        
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
        
        # Complete line stats built from the raw data
        self.line_stats: Dict[Tuple[str, str, int], LineStats] = {}
        
        # Root nodes (entry points with no parents)
        # self.root_lines: List[Tuple[str, str, int]] = []

    @property
    def root_lines(self) -> List[Tuple[str, str, int]]:
        """Get all root lines (lines with no parents)."""
        print("Root lines:", self.line_parents)
        return [key for key in self.line_parents if self.line_parents[key] is None]

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

        # Store source line if we haven't seen it yet
        if line_key not in self.line_source:
            try:
                with open(file_name, 'r') as f:
                    source_lines = f.readlines()
                    source = source_lines[line_no-1].strip() if 0 <= line_no-1 < len(source_lines) else "<line not available>"
                    self.line_source[line_key] = source
            except Exception:
                self.line_source[line_key] = "<source not available>"

        if event == 'call':

            logging.debug(f"-------\nFunction call: {line_key}")
            # Push the lne that did the call to the stack
            self.call_stack.append(self.last_line_key)
            logging.debug(f"added to call stack: {self.call_stack}\n----")
            # Record the entry point for this function

        
        elif event == 'line':
            logging.debug(f"-------\nLine execution: {line_key}")
            # Count this line hit
            self.line_hits[line_key] += 1
            
            # If we have a previous line, record its time
            if self.last_line_key and self.last_time:
                elapsed = (now - self.last_time) * 1000
                self.line_times[self.last_line_key] += elapsed
            
            # Establish parent relationship if we're in a function
            if self.call_stack:
                func_entry = self.call_stack[-1]
                # update parent child relations
                self.line_parents[line_key] = func_entry
                self.line_children[func_entry].add(line_key)
                
            
            # Store current line for next calculation
            self.last_line_key = line_key
            self.last_time = now
        
        elif event == 'return':
            logging.debug(f"-------\nFunction return: {line_key}")

            # If we have a line we're timing, record its final time
            if self.last_line_key and self.last_time:
                elapsed = (now - self.last_time) * 1000
                self.line_times[self.last_line_key] += elapsed
            
            # Pop from call stack if we're returning from a function
            if self.call_stack:
                self.call_stack.pop()
            
            self.last_line_key = self.call_stack[-1] if self.call_stack else None
            logging.debug(f"removed from call stack: {self.call_stack}\n----")
        
        else: 
            logging.debug(f"-------\nOther event: {event} for {line_key}")
        
        return self.trace_function
    
    def start_tracing(self) -> None:
        # Reset state
        self.__init__()
        # Start tracing
        sys.settrace(self.trace_function)
    
    def stop_tracing(self) -> None:
        sys.settrace(None)
        # Build the complete line stats
        self._build_line_stats()
  
    def _build_line_stats(self) -> None:
        """Build complete line statistics from the raw trace data."""
        # First, create all LineStats objects
        for line_key, time_spent in self.line_times.items():
            # Skip lines with negligible time
            if time_spent < 0.1:
                continue
            file_name, func_name, line_no = line_key
            hits = self.line_hits[line_key]
            source = self.line_source.get(line_key, "<source not available>")
            parent_key = self.line_parents.get(line_key)
            child_keys = list(self.line_children.get(line_key, set()))
            
                
            self.line_stats[line_key] = LineStats(
                file_name=file_name,
                function_name=func_name,
                line_no=line_no,
                hits=hits,
                time=time_spent,
                avg_time=time_spent / hits if hits else 0,
                source=source,
                parent_key=parent_key,
                child_keys=child_keys
            )
        
        # Next, calculate child_time for each line
        for line_key, stats in self.line_stats.items():
            child_time = 0.0
            for child_key in stats.child_keys:
                if child_key in self.line_stats:
                    child_time += self.line_stats[child_key].time
            
            stats.child_time = child_time
        
        # Calculate total program time
        self.total_time_ms = sum(stats.self_time for stats in self.line_stats.values())

    def get_line_stats(self, line_key: Tuple[str, str, int]) -> Optional[LineStats]:
        """Get statistics for a specific line."""
        return self.line_stats.get(line_key)
    
    def get_all_line_stats(self) -> Dict[Tuple[str, str, int], LineStats]:
        """Get statistics for all lines."""
        return self.line_stats
    
    def get_root_lines(self) -> List[LineStats]:
        """Get all root (entry point) lines."""
        return [self.line_stats[key] for key in self.root_lines if key in self.line_stats]
    
    def get_line_children(self, line_key: Tuple[str, str, int]) -> List[LineStats]:
        """Get all child lines of a specific line."""
        stats = self.line_stats.get(line_key)
        if not stats:
            return []
        
        return [self.line_stats[child_key] for child_key in stats.child_keys 
                if child_key in self.line_stats]
    
    def print_line_summary(self, current_file: Optional[str] = None, n: Optional[int] = None) -> None:
        """Print a summary of line execution times.
        
        Args:
            current_file: Optional[str] - If provided, only shows lines from this file.
            n: Optional[int] - If provided, only shows the top n longest-running lines.
        """
        if not self.line_stats:
            print("No lines were traced.")
            return
        
        # First, get all lines
        all_lines = list(self.line_stats.values())
        
        # Filter by file if requested
        if current_file:
            current_file = os.path.abspath(current_file)
            all_lines = [line for line in all_lines if os.path.abspath(line.file_name) == current_file]
            
            if not all_lines:
                print(f"No lines traced in file: {os.path.basename(current_file)}")
                return
        
        # Sort lines by self_time (descending)
        all_lines.sort(key=lambda x: x.self_time, reverse=True)
        
        # Limit to top n if specified
        if n is not None and len(all_lines) > n:
            all_lines = all_lines[:n]
        
        # Calculate total time for percentage calculation
        displayed_total = sum(line.self_time for line in all_lines)
        
        # Create title based on filtering
        title = "LINE EXECUTION TIME SUMMARY"
        if current_file:
            title += f" FOR: {os.path.basename(current_file)}"
        if n is not None:
            title += f" (TOP {n})"
        
        # Print the summary
        print("\n\n============================================================")
        print(title)
        print("============================================================")
        print(f"| {'Line':^40} | {'Self(ms)':>10} | {'Total(ms)':>10} | {'%':>6} |")
        print('-' * 78)
        
        for line in all_lines:
            # Get just the filename without path
            filename = os.path.basename(line.file_name)
            line_id = f"{filename}::{line.function_name}::{line.line_no}"
            
            # Calculate percentage relative to displayed total
            percent = (line.self_time / displayed_total * 100) if displayed_total > 0 else 0
            
            print(f"| {line_id:40} | {line.self_time:>10.3f} | {line.total_time:>10.3f} | {percent:>6.1f}% |")
        
        print('-' * 78)
        print(f"| {'DISPLAYED TOTAL':40} | {displayed_total:>10.3f} |            | 100.0% |")
        print("============================================================")
        
    # Update the call tree method to order lines by line number within the same file
    def print_call_tree(self, root_key: Optional[Tuple[str, str, int]] = None, depth: int = 0, max_depth: int = 10) -> None:
        """Print a call tree starting from a specific line or from all roots.
        
        Args:
            root_key: Optional[Tuple[str, str, int]] - If provided, start from this line.
                                                    If None, start from all root lines.
            depth: int - Current recursion depth (for internal use).
            max_depth: int - Maximum depth to display.
        """
        if depth > max_depth:
            return  # Prevent infinite recursion
            
        indent = "  " * depth
        
        if root_key:
            # Print a specific subtree
            if root_key not in self.line_stats:
                print(f"{indent}Line {root_key} not found in stats")
                return
                
            line = self.line_stats[root_key]
            filename = os.path.basename(line.file_name)
            line_id = f"{filename}::{line.function_name}::{line.line_no}"
            
            print(f"{indent}{line_id} [self:{line.self_time:.2f}ms total:{line.total_time:.2f}ms] - {line.source}")
            
            # Get all child lines
            child_lines = [self.line_stats[child_key] for child_key in line.child_keys 
                        if child_key in self.line_stats]
            
            # Group children by file
            children_by_file = {}
            for child in child_lines:
                if child.file_name not in children_by_file:
                    children_by_file[child.file_name] = []
                children_by_file[child.file_name].append(child)
            
            # Sort each file's lines by line number
            for file_name in children_by_file:
                children_by_file[file_name].sort(key=lambda x: x.line_no)
            
            # Sort files by total time (descending)
            files_by_time = sorted(
                children_by_file.keys(),
                key=lambda f: sum(c.total_time for c in children_by_file[f]),
                reverse=True
            )
            
            # Print child lines in order
            for file_name in files_by_time:
                for child in children_by_file[file_name]:
                    self.print_call_tree(child.key, depth + 1, max_depth)
        else:
            # Print all root trees
            root_lines = self.get_root_lines()
            if not root_lines:
                print("No root lines found in stats")
                return
                
            print("\n\nCALL TREE (SELF TIME / TOTAL TIME):")
            print("====================================")
            
            # Sort roots by total time
            root_lines.sort(key=lambda x: x.total_time, reverse=True)
            
            for root in root_lines:
                self.print_call_tree(root.key, 0, max_depth)
                print()  # Empty line between roots
    
    def print_line_details(self, line_key: Tuple[str, str, int]) -> None:
        """Print detailed statistics for a specific line and its children."""
        if line_key not in self.line_stats:
            print(f"Line {line_key} not found in stats")
            return
        
        line = self.line_stats[line_key]
        children = self.get_line_children(line_key)
        children.sort(key=lambda x: x.total_time, reverse=True)
        
        filename = os.path.basename(line.file_name)
        line_id = f"{filename}::{line.function_name}::{line.line_no}"
        
        print(f"\n\n============================================================")
        print(f"LINE DETAILS: {line_id}")
        print(f"============================================================")
        print(f"Source: {line.source}")
        print(f"Hits: {line.hits}")
        print(f"Self time: {line.self_time:.3f}ms")
        print(f"Child time: {line.child_time:.3f}ms")
        print(f"Total time: {line.total_time:.3f}ms")
        
        if not children:
            print("\nNo child calls from this line")
            return
            
        print("\nChild calls from this line:")
        print(f"| {'Child Line':^40} | {'Self(ms)':>10} | {'Total(ms)':>10} | {'%':>6} |")
        print('-' * 78)
        
        total_child_time = sum(child.total_time for child in children)
        
        for child in children:
            child_filename = os.path.basename(child.file_name)
            child_id = f"{child_filename}::{child.function_name}::{child.line_no}"
            
            # Calculate percentage relative to total child time
            percent = (child.total_time / total_child_time * 100) if total_child_time > 0 else 0
            
            print(f"| {child_id:40} | {child.self_time:>10.3f} | {child.total_time:>10.3f} | {percent:>6.1f}% |")
        
        print('-' * 78)
        print(f"| {'TOTAL CHILD TIME':40} | {' ':10} | {total_child_time:>10.3f} | 100.0% |")
        print("============================================================")


# Create a singleton instance for the module
tracer = CodeTracer()

def set_custom_trace() -> None:
    """Start tracing code execution."""
    tracer.start_tracing()

def stop_custom_trace() -> None:
    """Stop tracing code execution."""
    tracer.stop_tracing()

def print_summary(n: Optional[int] = None) -> None:
    """Print a summary of the most time-consuming lines in the current file.
    
    Args:
        n: Optional[int] - If provided, only shows the top n lines.
    """
    # Get the current file path using inspection
    import inspect
    caller_frame = inspect.currentframe().f_back
    current_file = caller_frame.f_code.co_filename if caller_frame else None
    
    tracer.print_line_summary(current_file=current_file, n=n)

def print_all_lines(n: Optional[int] = None) -> None:
    """Print a summary of all traced lines across all files.
    
    Args:
        n: Optional[int] - If provided, only shows the top n lines.
    """
    tracer.print_line_summary(n=n)

def print_call_tree() -> None:
    """Print the complete call tree of traced execution."""
    tracer.print_call_tree()

def print_line_details(file_name: str, function_name: str, line_no: int) -> None:
    """Print detailed statistics for a specific line.
    
    Args:
        file_name: str - File containing the line
        function_name: str - Function containing the line
        line_no: int - Line number
    """
    tracer.print_line_details((file_name, function_name, line_no))