import curses
import os
from typing import List, Dict, Tuple, Optional, Callable, Any

class TerminalTreeUI:
    """A terminal UI for displaying and interacting with tree data."""
    
    def __init__(self, tree_data_provider: Callable, node_formatter: Callable):
        """
        Initialize the terminal UI.
        
        Args:
            tree_data_provider: Callable that returns the tree data to display
            node_formatter: Callable that formats a node for display
        """
        self.tree_data_provider = tree_data_provider
        self.node_formatter = node_formatter
        
        # Tree branch characters
        self.branch_mid = "├── "
        self.branch_last = "└── "
        self.pipe = "│   "
        self.space = "    "
        
        # UI state
        self.expanded_nodes = set()  # Keys of expanded nodes (instead of collapsed)
        self.current_pos = 0         # Current selected position
        self.scroll_offset = 0       # Vertical scroll offset
        
    def _generate_display_data(self, root_nodes):
        """Generate flattened display data based on current UI state."""
        display_data = []
        
        # Process each root node
        for i, root in enumerate(root_nodes):
            is_last_root = (i == len(root_nodes) - 1)
            
            # Add root node
            node_data = {
                'line': root,
                'depth': 0,
                'is_last': is_last_root,
                'has_children': bool(root.child_keys)
            }
            display_data.append(node_data)
            
            # Add children only if explicitly expanded
            if root.key in self.expanded_nodes:
                self._add_children_to_display(display_data, root, 1)
        
        return display_data
    
    def _add_children_to_display(self, display_data, parent, depth):
        """Add children of a node to the display data recursively."""
        # Get all child lines
        child_lines = self._get_sorted_children(parent)
        
        # Add each child to display data
        for i, child in enumerate(child_lines):
            is_last_child = (i == len(child_lines) - 1)
            
            node_data = {
                'line': child,
                'depth': depth,
                'is_last': is_last_child,
                'has_children': bool(child.child_keys)
            }
            display_data.append(node_data)
            
            # Add child's children only if explicitly expanded
            if child.key in self.expanded_nodes:
                self._add_children_to_display(display_data, child, depth + 1)
    
    def _get_sorted_children(self, parent):
        """Get children of a parent node."""
        # First get all valid children
        children = self.tree_data_provider(parent.key)
        
        # Group children by file
        children_by_file = {}
        for child in children:
            if child.file_name not in children_by_file:
                children_by_file[child.file_name] = []
            children_by_file[child.file_name].append(child)
        
        # Sort each file's lines by line number
        for file_name in children_by_file:
            children_by_file[file_name].sort(key=lambda x: x.line_no)
        
        # Flatten all children
        all_children = []
        for file_name in children_by_file:
            all_children.extend(children_by_file[file_name])
        
        return all_children
    
    def _render_tree(self, stdscr, display_data, max_y, max_x):
        """Render the tree data on the screen."""
        # Limit display data to visible area
        visible_height = max_y - 4  # Account for header and help
        
        # Initialize screen position and map of rows that need spacing
        screen_y = 2  # Start after header
        root_spacers = set()  # Track where to add blank lines
        
        # Find where are the root nodes
        # and add spacers for them
        for i, node in enumerate(display_data):
            if i > 0 and node['depth'] == 0:
                # This is a new root node, add a spacer before it
                root_spacers.add(i)
        
        
        # Calculate visible range accounting for spacers
        visible_end = self.scroll_offset
        visible_items = 0
        for i in range(self.scroll_offset, len(display_data)):
            if visible_items >= visible_height:
                break
            visible_end = i + 1
            visible_items += 1
            if i + 1 in root_spacers:
                visible_items += 1  # Count the spacer
        
        # Render the visible portion
        rendered_pos = 0
        for i in range(self.scroll_offset, visible_end):
            # Add a blank line before root nodes (except the first one)
            if i in root_spacers:
                screen_y += 1
                rendered_pos += 1
            
            node = display_data[i]
            
            # Calculate screen position
            abs_pos = i
            
            # Color based on selection
            color = curses.color_pair(2) if abs_pos == self.current_pos else curses.color_pair(1)
            
            # Generate prefix based on depth and position
            prefix = self._get_prefix(node, display_data)
            
            # Get indicator for expandable nodes
            indicator = ""
            if node['has_children']:
                indicator = "[+] " if node['line'].key not in self.expanded_nodes else "[-] "
            
            # Format the node using the provided formatter
            line_text = self.node_formatter(node['line'], indicator)
            
            # Combine and truncate if needed
            full_line = f"{prefix}{line_text}"
            if len(full_line) >= max_x:
                full_line = full_line[:max_x-3] + "..."
            
            # Add to screen
            stdscr.addstr(screen_y, 0, full_line, color)
            screen_y += 1
            rendered_pos += 1
    
    def _get_prefix(self, node, display_data):
        """Generate the tree prefix for a node based on its position in the hierarchy."""
        prefix = ""
        if node['depth'] == 0:
            # Root nodes
            return self.branch_last if node['is_last'] else self.branch_mid
        
        # For each level of depth, determine if we need a pipe or space
        for d in range(node['depth']+1):
            if d == node['depth']:
                # Last level - add branch
                prefix += self.branch_last if node['is_last'] else self.branch_mid
            else:
                # Find if any parent at this level is a last child
                is_last_ancestor = self._check_if_last_ancestor(node, display_data, d)
                prefix += self.space if is_last_ancestor else self.pipe
        
        return prefix
    
    def _check_if_last_ancestor(self, node, display_data, depth):
        """Check if the node has an ancestor at the given depth that is the last child."""
        # Find all nodes at this depth level
        nodes_at_depth = [n for n in display_data if n['depth'] == depth]
        if not nodes_at_depth:
            return False
            
        # Get the last node at this depth that appears before our target node
        for n in reversed(nodes_at_depth):
            if display_data.index(n) < display_data.index(node):
                return n['is_last']
        
        return False
    
    def _toggle_collapse(self, display_data, current_node):
        """Toggle collapse state of the current node."""
        node_key = current_node['line'].key
        if node_key in self.expanded_nodes:
            self.expanded_nodes.remove(node_key)
        else:
            self.expanded_nodes.add(node_key)
    
    def run(self):
        """Run the terminal UI."""
        curses.wrapper(self._main_curses_loop)
    
    def _main_curses_loop(self, stdscr):
        """Main curses loop for displaying and interacting with the tree."""
        # Initialize curses
        stdscr.clear()
        curses.curs_set(0)  # Hide cursor
        curses.start_color()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Normal text
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Highlighted text
        curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Headers
        
        # Get root data from provider
        root_nodes = self.tree_data_provider()
        
        # Header and help text
        help_text = "[↑/↓]: Navigate | [Enter]: Expand/Collapse | [q]: Quit"
        
        # Main UI loop
        running = True
        while running:
            # Get terminal dimensions
            max_y, max_x = stdscr.getmaxyx()
            
            # Clear screen
            stdscr.clear()
            
            # Generate display data
            display_data = self._generate_display_data(root_nodes)
            
            # Display header
            header = "LINE TRACE TREE"
            stdscr.addstr(0, 0, header, curses.color_pair(3) | curses.A_BOLD)
            stdscr.addstr(1, 0, "=" * len(header), curses.color_pair(3))
            
            # Display tree
            self._render_tree(stdscr, display_data, max_y, max_x)
            
            # Display help
            stdscr.addstr(max_y-1, 0, help_text, curses.color_pair(3))
            
            # Refresh screen
            stdscr.refresh()
            
            # Get user input
            key = stdscr.getch()
            
            # Handle key presses
            if key == curses.KEY_UP:
                # Move up
                if self.current_pos > 0:
                    self.current_pos -= 1
                    # Adjust scroll if needed
                    if self.current_pos < self.scroll_offset:
                        self.scroll_offset = self.current_pos
            
            elif key == curses.KEY_DOWN:
                # Move down
                if self.current_pos < len(display_data) - 1:
                    self.current_pos += 1
                    # Adjust scroll if needed
                    visible_height = max_y - 4
                    if self.current_pos >= self.scroll_offset + visible_height:
                        self.scroll_offset = self.current_pos - visible_height + 1
            
            elif key == ord('\n'):  # Enter key
                # Toggle collapse state
                if self.current_pos < len(display_data):
                    current_node = display_data[self.current_pos]
                    if current_node['has_children']:
                        self._toggle_collapse(display_data, current_node)
            
            elif key == ord('q'):  # Quit
                running = False