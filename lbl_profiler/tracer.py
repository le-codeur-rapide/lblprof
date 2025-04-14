import logging
logging.basicConfig(level=logging.DEBUG)
import sys
import time
import os
from typing import Dict, List, Tuple, Any
from .line_stat_tree import LineStats, LineStatsTree


class CodeTracer:
    def __init__(self):
        # We use a dictionary to store the source code of lines
        self.line_source: Dict[Tuple[str, str, int], str] = {}
        
        # Call stack to handle nested calls
        self.call_stack: List[Tuple[str, str, int]] = []
        
        # Current line tracking
        self.last_time: float = time.time()
        
        # We use this to not try to trace modules not written by the user
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
        
        # We use this to store the tree of line stats
        self.tree = LineStatsTree()

        # Use to store the line info until next line to have the time of the line
        self.tempo_line_infos = None 

    def trace_function(self, frame: Any, event: str, arg: Any) -> Any:
        # main function that will replace the default trace function 
        # using sys.settrace
        frame.f_trace_opcodes = True
        code = frame.f_code
        func_name = code.co_name
        file_name = code.co_filename
        line_no = frame.f_lineno

        # Skip installed modules
        if self._is_installed_module(file_name):
            return None
        
        # Get time and create key
        now = time.time()
        line_key = (file_name, func_name, line_no)

        # Get or store source code of the line
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
            # A function is called

            # Get caller info (line that calls the function)
            caller_file = frame.f_back.f_code.co_filename
            caller_func = frame.f_back.f_code.co_name
            caller_line = frame.f_back.f_lineno
            caller_key = (caller_file, caller_func, caller_line)

            # Update call stack
            # Until we return from the function, all lines executed will have
            # the caller line as parent
            self.call_stack.append(caller_key)

        elif event == 'line':
            logging.debug(f"Tracing line {line_no} in {file_name} ({func_name})")
            # A line of code is executed
            parent_key = self.call_stack[-1]
            if not self.tempo_line_infos:
                # This is the first line executed, there is no new duration to store in the tree, 
                # we just store the current line info
                self.tempo_line_infos = (file_name, func_name, line_no, source, parent_key)
                return self.trace_function
            
            # If we have a previous line, we can calculate the time elapsed for it and 
            # add it to the tree
            elapsed = (now - self.last_time) * 1000
            self.tree.update_line_event(
                file_name=self.tempo_line_infos[0],
                function_name=self.tempo_line_infos[1],
                line_no=self.tempo_line_infos[2],
                hits=1,
                time_ms=elapsed,
                source=self.tempo_line_infos[3],
                parent_key=self.tempo_line_infos[4]
            )
            
            # Store current line info for next line + reset last_time
            self.last_time = now
            self.tempo_line_infos = (file_name, func_name, line_no, source, parent_key)
            
        elif event == 'return':
            logging.debug(f"Returning from {func_name} in {file_name} ({line_no})")
            # A function is returning
            # We just need to pop the last line from the call stack so newt
            # lines will have the correct parent 
            if self.call_stack:
                self.call_stack.pop()
            
            # We still need to update time and last infos for the next line
            # This is what I found for now, problem is that if some computation is made at return line, 
            # we don't know it
            self.last_time = now
            parent_key = self.call_stack[-1] if self.call_stack else None
            self.tempo_line_infos = None
            
        # We need to return the trace function to continue tracing
        # https://docs.python.org/3.8/library/sys.html#sys.settrace:~:text=The%20local%20trace%20function%20should
        return self.trace_function
    
    def start_tracing(self) -> None:
        # Reset state
        self.__init__()
        sys.settrace(self.trace_function)
    
    def stop_tracing(self) -> None:
        sys.settrace(None)
  
    def _is_installed_module(self, filename: str) -> bool:
        """Check if a file belongs to an installed module rather than user code."""
        return any(path in filename for path in self.site_packages_paths) or len(filename) ==   0
    
