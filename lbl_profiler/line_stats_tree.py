import logging
import os
from typing import List, Dict, Tuple, Optional

from pydantic import BaseModel, Field, ConfigDict

from lbl_profiler.terminal_ui import TerminalTreeUI


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
    
    # Parent line that called this function
    # If None then it 
    parent_key: Optional[Tuple[str, str, int]] = None
    
    # Children lines called by this line (populated during analysis)
    child_keys: List[Tuple[str, str, int]] = Field(default_factory=list)
    
    @property
    def key(self) -> Tuple[str, str, int]:
        """Get the unique key for this line."""
        return (self.file_name, self.function_name, self.line_no)
    
    @property
    def extended_key(self) -> Tuple:
        """Get an extended unique key that includes parent information."""
        return (self.file_name, self.function_name, self.line_no, self.parent_key)
    
    @property
    def self_time(self) -> float:
        """Get time spent on this line excluding child calls."""
        return max(0.0, self.time - self.child_time)
    
    @property
    def total_time(self) -> float:
        """Get total time including child calls."""
        return self.time


class LineStatsTree:
    """A tree structure to manage LineStats objects with automatic parent-child time propagation."""
    
    def __init__(self):
        # Store all lines by their key
        self.lines: Dict[Tuple[str, str, int], LineStats] = {}
        
        # Track root nodes (entry points with no parents)
        self.root_lines: List[Tuple[str, str, int]] = []
        
        # Total time for all tracked lines
        self.total_time_ms: float = 0
    
    
    def _update_parent_times(self, parent_key: Tuple[str, str, int], time_delta: float) -> None:
        """Recursively update the time of a parent line and all its ancestors.
        
        Args:
            parent_key: Tuple[str, str, int] - Key of the parent line
            time_delta: float - Time difference to add in milliseconds
        """
        if parent_key not in self.lines:
            return
        
        # Update parent time
        parent = self.lines[parent_key]
        parent.time += time_delta
        
        # Calculate new child_time
        child_time = sum(self.lines[child_key].time 
                        for child_key in parent.child_keys 
                        if child_key in self.lines)
        parent.child_time = child_time
        
        # Continue up the tree
        if parent.parent_key:
            self._update_parent_times(parent.parent_key, time_delta)
    
    def update_line_time(self, line_key: Tuple[str, str, int], 
                        additional_time: float, additional_hits: int = 0) -> None:
        """Update the time and hit count for a specific line.
        
        Args:
            line_key: Tuple[str, str, int] - Key of the line to update
            additional_time: float - Additional time to add in milliseconds
            additional_hits: int - Additional hit count to add
        """
        logging.debug(f"Updating line time: {line_key} [additional hits:{additional_hits} additional time:{additional_time:.2f}ms]")
        if line_key not in self.lines:
            # Line doesn't exist, can't update
            return
        
        # Update the line
        line = self.lines[line_key]
        line.time += additional_time
        line.hits += additional_hits
        if line.hits > 0:
            line.avg_time = line.time / line.hits
        
        # Update parent times
        if line.parent_key:
            self._update_parent_times(line.parent_key, additional_time)
        
        # Update total time
        self.total_time_ms += additional_time
    
    def create_line(self, file_name: str, function_name: str, line_no: int,
                   hits: int, time_ms: float, source: str,
                   parent_key: Optional[Tuple[str, str, int]] = None) -> None:
        """Create a new LineStats object and add it to the tree.
        
        Args:
            file_name: str - File containing the line
            function_name: str - Function containing the line
            line_no: int - Line number
            hits: int - Number of times line was executed
            time_ms: float - Time spent on this line in milliseconds
            source: str - Source code for this line
            parent_key: Optional[Tuple[str, str, int]] - Key of the parent line
            
        Returns:
            LineStats - The created LineStats object
        """
        logging.debug(f"Creating line: {file_name}::{function_name}::{line_no} [hits:{hits} time:{time_ms:.2f}ms]")
        # Create the LineStats object
        line_stats = LineStats(
            file_name=file_name,
            function_name=function_name,
            line_no=line_no,
            hits=hits,
            time=time_ms,
            avg_time=time_ms / hits if hits else 0,
            source=source,
            parent_key=parent_key,
            child_keys=[]
        )
        
        # Add the line to the dictionary
        self.lines[line_stats.key] = line_stats
        
        # If this is a root line, add it to root_lines
        if line_stats.parent_key is None:
            self.root_lines.append(line_stats.key)

            # If it is root, it has no ancestor to update, so we can return
            return
        else:
            # If this line has a parent, add it as a child of the parent
            self.lines[line_stats.parent_key].child_keys.append(line_stats.key)

        # Update the time of ancestors
        self._update_parent_times(line_stats.parent_key, line_stats.time)
        return 
    
    
    def _get_root_lines(self) -> List[LineStats]:
        """Get all root LineStats objects (with no parents).
        
        Returns:
            List[LineStats] - All root LineStats objects
        """
        return [self.lines[key] for key in self.root_lines if key in self.lines]

    def _get_source_code(self, file_name: str, line_no: int) -> str:
        """Get the source code for a specific line in a file."""
        # At this point the source lines should be given by the tracer
        # because it has the ability to kind of cache it. We ust this 
        # method only in edge cases where we need don't have it (ex root lines)
        # Idealy we don't need this method at all.
        with open(file_name, 'r') as f:
            lines = f.readlines()
            if line_no - 1 < len(lines):
                return lines[line_no - 1].strip()
            else:
                return ""
    

    def update_line_event(self, file_name: str, function_name: str, line_no: int, 
                 hits: int, time_ms: float, source: str, 
                 parent_key: Tuple[str, str, int]) -> None:
        """Update the tree with a line execution event.
        
        Args:
            file_name: Path to the file containing the line
            function_name: Name of the function containing the line
            line_no: Line number in the file
            hits: Number of times the line was hit
            time_ms: Execution time in milliseconds
            source: Source code of the line
            parent_key: Key of the parent line in the call stack, or None if this is a root
        """
        logging.debug(f"Updating line event: {file_name}::{function_name}::{line_no} [hits:{hits} time:{time_ms:.2f}ms]")
        # Basic line key (without parent information)
        line_key = (file_name, function_name, line_no)

        # Check if the parent exists and create it if needed
        if parent_key not in self.lines:
            # If parent doesn't exist, create it
            self.create_line(
                file_name=parent_key[0],
                function_name=parent_key[1],
                line_no=parent_key[2],
                hits=0,
                time_ms=0,
                source=self._get_source_code(
                    file_name=parent_key[0],
                    line_no=parent_key[2]
                ),
                parent_key=None  # No parent for this parent (might need to be adjusted)
            )
        
        # Find the line by its extended key (same line but with specific parent)
        for existing_key, existing_line in self.lines.items():
            if existing_key[:3] == line_key and existing_line.parent_key == parent_key:
                # We found the same line with same parent - update it
                self.update_line_time(existing_key, time_ms, hits)
                return
                
        # If we get here, we didn't find the line with this specific parent - create it
        self.create_line(
            file_name=file_name,
            function_name=function_name,
            line_no=line_no,
            hits=hits,
            time_ms=time_ms,
            source=source,
            parent_key=parent_key
        )
        
        # Make sure the parent-child relationship is established
        if parent_key and line_key not in self.lines[parent_key].child_keys:
            self.lines[parent_key].child_keys.append(line_key)
            

    def display_tree(self, root_key: Optional[Tuple[str, str, int]] = None, depth: int = 0, 
                    max_depth: int = 10, is_last: bool = True, prefix: str = "") -> None:
        """Display a visual tree showing parent-child relationships between lines.
        
        Args:
            root_key: Optional[Tuple[str, str, int]] - If provided, start from this line.
                                                    If None, start from all root lines.
            depth: int - Current recursion depth (for internal use).
            max_depth: int - Maximum depth to display.
            is_last: bool - Whether this node is the last child of its parent (for drawing)
            prefix: str - The prefix string for the current line (for drawing)
        """
        if depth > max_depth:
            return  # Prevent infinite recursion
        
        # Tree branch characters
        branch_mid = "├── "
        branch_last = "└── "
        pipe = "│   "
        space = "    "
        
        if root_key:
            # Print a specific subtree
            if root_key not in self.lines:
                print(f"{prefix}{'?' * 40} [Line not found in stats]")
                return
                
            line = self.lines[root_key]
            filename = os.path.basename(line.file_name)
            line_id = f"{filename}::{line.function_name}::{line.line_no}"
            
            # Truncate source code
            truncated_source = line.source[:60] + "..." if len(line.source) > 60 else line.source
            
            # Display current line with time info, hits count and source on the same line
            branch = branch_last if is_last else branch_mid
            print(f"{prefix}{branch}{line_id} [hits:{line.hits} self:{line.self_time:.2f}ms total:{line.total_time:.2f}ms] - {truncated_source}")
            
            # Get all child lines
            child_lines = [self.lines[child_key] for child_key in line.child_keys 
                        if child_key in self.lines]
            
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
            
            # Track whether a child is the last one to be displayed
            all_children = []
            for file_name in files_by_time:
                all_children.extend(children_by_file[file_name])
            
            # Display child lines in order
            next_prefix = prefix + (space if is_last else pipe)
            for i, child in enumerate(all_children):
                is_last_child = (i == len(all_children) - 1)
                self.display_tree(child.key, depth + 1, max_depth, is_last_child, next_prefix)
        else:
            # Print all root trees
            root_lines = self._get_root_lines()
            if not root_lines:
                print("No root lines found in stats")
                return
                
            print("\n\nLINE TRACE TREE (HITS / SELF TIME / TOTAL TIME):")
            print("=================================================")
            
            # Sort roots by total time (descending)
            root_lines.sort(key=lambda x: x.total_time, reverse=True)
            
            # For each root, render as a separate tree with branch characters
            for i, root in enumerate(root_lines):
                is_last_root = (i == len(root_lines) - 1)
                branch = branch_last if is_last_root else branch_mid
                
                filename = os.path.basename(root.file_name)
                line_id = f"{filename}::{root.function_name}::{root.line_no}"
                
                # Truncate source code
                truncated_source = root.source[:60] + "..." if len(root.source) > 60 else root.source
                
                # Display root line with hits count
                print(f"{branch}{line_id} [hits:{root.hits} self:{root.self_time:.2f}ms total:{root.total_time:.2f}ms] - {truncated_source}")
                
                # Get all child lines
                child_lines = [self.lines[child_key] for child_key in root.child_keys 
                            if child_key in self.lines]
                
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
                
                # Track whether a child is the last one to be displayed
                all_children = []
                for file_name in files_by_time:
                    all_children.extend(children_by_file[file_name])
                
                # Display child lines in order
                next_prefix = space if is_last_root else pipe
                for j, child in enumerate(all_children):
                    is_last_child = (j == len(all_children) - 1)
                    self.display_tree(child.key, 1, max_depth, is_last_child, next_prefix)
                
                # Add empty line between roots
                if not is_last_root:
                    print()
    def show_interactive(self):
        """Display the tree in an interactive terminal interface."""
        
        # Define the data provider 
        # Given a node (a line), return its children
        def get_tree_data(node_key=None):
            if node_key is None:
                # Return root nodes
                return self._get_root_lines()
            else:
                # Return children of the specified node
                return [self.lines[child_key] for child_key in self.lines[node_key].child_keys 
                        if child_key in self.lines]
        
        # Define the node formatter function
        # Given a line, return its formatted string (displayed in the UI)
        def format_node(line, indicator=""):
            filename = os.path.basename(line.file_name)
            line_id = f"{filename}::{line.function_name}::{line.line_no}"
            
            # Truncate source code
            truncated_source = line.source[:40] + "..." if len(line.source) > 40 else line.source
            
            # Format stats
            stats = f"[hits:{line.hits} self:{line.self_time:.2f}ms total:{line.total_time:.2f}ms]"
            
            # Return formatted line
            return f"{indicator}{line_id} {stats} - {truncated_source}"
        
        # Create and run the UI
        ui = TerminalTreeUI(get_tree_data, format_node)
        ui.run()