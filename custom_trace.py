import logging
logging.basicConfig(level=logging.DEBUG)
import sys
import time
import os
from typing import Dict, List, Tuple, Any
from line_stat_tree import LineStats, LineStatsTree


class CodeTracer:
    def __init__(self):
        # Data structures to store trace information - everything is lines now
        self.line_source: Dict[Tuple[str, str, int], str] = {}
        
        # Call stack to handle nested calls
        self.call_stack: List[Tuple[str, str, int]] = []
        
        # Current line tracking
        self.last_time: float = time.time()
        
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
        self.root_lines: List[Tuple[str, str, int]] = []
        self.tree = LineStatsTree()

        self.tempo_line_infos = None # Use to store the line info until next line to have the time of the line

    def is_installed_module(self, filename: str) -> bool:
        """Check if a file belongs to an installed module rather than user code."""
        return any(path in filename for path in self.site_packages_paths) or len(filename) ==   0
    
    def trace_function(self, frame: Any, event: str, arg: Any) -> Any:
        frame.f_trace_opcodes = True
        code = frame.f_code
        func_name = code.co_name
        file_name = code.co_filename
        line_no = frame.f_lineno

        self.tree.display_tree()
        
        # Skip installed modules
        if self.is_installed_module(file_name):
            return None
        
        # Get time and create key
        now = time.time()
        line_key = (file_name, func_name, line_no)

        # Get or store source
        if line_key not in self.line_source:
            try:
                with open(file_name, 'r') as f:
                    source_lines = f.readlines()
                    source = source_lines[line_no-1].strip() if 0 <= line_no-1 < len(source_lines) else "<line not available>"
                    self.line_source[line_key] = source
            except Exception:
                self.line_source[line_key] = "<source not available>"
        source = self.line_source[line_key]

        if event == 'call':
            
            # Get caller info
            caller_file = frame.f_back.f_code.co_filename
            caller_func = frame.f_back.f_code.co_name
            caller_line = frame.f_back.f_lineno
            caller_key = (caller_file, caller_func, caller_line)

            # Update call stack
            self.call_stack.append(caller_key)
            logging.debug(f"-------\nFunction call: {line_key}")
            logging.debug(f"new call stack: {self.call_stack}")

        elif event == 'line':
            prev_file_name, prev_func_name, prev_line_no, prev_source, prev_parent_key = self.tempo_line_infos if self.tempo_line_infos else (None, None, None, None, None)
            parent_key = self.call_stack[-1] if self.call_stack else None
            elapsed = (now - self.last_time) * 1000
            if prev_file_name is None:
                self.tempo_line_infos = (file_name, func_name, line_no, source, parent_key)
            else:
            
                self.tree.update_line_event(
                    file_name=prev_file_name,
                    function_name=prev_func_name,
                    line_no=prev_line_no,
                    hits=1,
                    time_ms=elapsed,
                    source=prev_source,
                    parent_key=prev_parent_key
                )
                
                self.last_time = now
                self.tempo_line_infos = (file_name, func_name, line_no, source, parent_key)
                logging.debug(f"-------\nLine execution: {line_key}")
            
        elif event == 'return':
            # Update call stack
            if self.call_stack:
                self.call_stack.pop()
            
            logging.debug(f"-------\nFunction return: {line_key}")
            logging.debug(f"new call stack: {self.call_stack}")
        return self.trace_function
    
    def start_tracing(self) -> None:
        # Reset state
        self.__init__()
        sys.settrace(self.trace_function)
    
    def stop_tracing(self) -> None:
        sys.settrace(None)
  
    
# Create a singleton instance for the module
tracer = CodeTracer()

def set_custom_trace() -> None:
    """Start tracing code execution."""
    tracer.start_tracing()

def stop_custom_trace() -> None:
    """Stop tracing code execution."""
    tracer.stop_tracing()

