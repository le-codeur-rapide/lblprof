import curses
import sys
from collections.abc import Callable
from typing import TypedDict

from lblprof.line_stat_object import EventKeyT, LineStats
from lblprof.print_tree import get_sorted_children
from lblprof.utils.visual_constants import (
    BRANCH_LAST_CHARS,
    BRANCH_MID_CHARS,
    PIPE_CHARS,
    SPACE_CHARS,
)

TUI_HELP_TEXT = (
    "[↑/↓]: Navigate | [PgUp/PgDn]: Page | [Enter]: Expand/Collapse | [q]: Quit"
)


class NodeTerminalUI(TypedDict):
    line: LineStats
    depth: int
    is_last: bool
    has_children: bool


def add_children_to_display(
    tree_data_provider: Callable[[LineStats | None], list[LineStats]],
    expanded_nodes: set[EventKeyT],
    display_data: list[NodeTerminalUI],
    parent: LineStats,
    depth: int,
) -> None:
    """Add children of a node to the display data recursively."""
    # Get all child lines
    children = tree_data_provider(parent)
    child_lines = get_sorted_children(children)

    # Add each child to display data
    for i, child in enumerate(child_lines):
        node_data: NodeTerminalUI = {
            "line": child,
            "depth": depth,
            "is_last": i == len(child_lines) - 1,
            "has_children": bool(child.childs),
        }
        display_data.append(node_data)

        # Add child's children only if explicitly expanded
        if child.event_key in expanded_nodes:
            add_children_to_display(
                tree_data_provider,
                expanded_nodes,
                display_data,
                child,
                depth + 1,
            )


def generate_display_data(
    root_nodes: list[LineStats],
    expanded_nodes: set[EventKeyT],
    tree_data_provider: Callable[[LineStats | None], list[LineStats]],
) -> list[NodeTerminalUI]:
    """Generate flattened display data based on current UI state."""
    display_data: list[NodeTerminalUI] = []

    # Process each root node
    for i, root in enumerate(root_nodes):
        node_data: NodeTerminalUI = {
            "line": root,
            "depth": 0,
            "is_last": i == len(root_nodes) - 1,
            "has_children": bool(root.childs),
        }
        display_data.append(node_data)

        # Add children only if explicitly expanded
        if root.event_key in expanded_nodes:
            add_children_to_display(
                tree_data_provider,
                expanded_nodes,
                display_data,
                root,
                1,
            )

    return display_data


def is_last_ancestor(
    node: NodeTerminalUI,
    display_data: list[NodeTerminalUI],
    depth: int,
) -> bool:
    """Check if the node has an ancestor at the given depth that is the last
    child."""
    # Find all nodes at this depth level
    nodes_at_depth = [n for n in display_data if n["depth"] == depth]
    if not nodes_at_depth:
        return False

    # Get the last node at this depth that appears before our target node
    for n in reversed(nodes_at_depth):
        if display_data.index(n) < display_data.index(node):
            return n["is_last"]

    return False


def get_prefix(
    node: NodeTerminalUI,
    display_data: list[NodeTerminalUI],
) -> str:
    """Generate the tree prefix for a node based on its position in the
    hierarchy."""
    prefix = ""
    if node["depth"] == 0:
        # Root nodes
        return BRANCH_LAST_CHARS if node["is_last"] else BRANCH_MID_CHARS

    # For each level of depth, determine if we need a pipe or space
    for d in range(node["depth"] + 1):
        if d == node["depth"]:
            # Last level - add branch
            prefix += BRANCH_LAST_CHARS if node["is_last"] else BRANCH_MID_CHARS
        else:
            # Find if any parent at this level is a last child
            prefix += (
                SPACE_CHARS if is_last_ancestor(node, display_data, d) else PIPE_CHARS
            )

    return prefix


class TerminalTreeUI:
    """A terminal UI for displaying and interacting with tree data."""

    def __init__(
        self,
        tree_data_provider: Callable[[LineStats | None], list[LineStats]],
        node_formatter: Callable[[LineStats, str], str],
    ) -> None:
        """
        Initialize the terminal UI.

        Args:
            tree_data_provider: Callable that returns the tree data to display
            node_formatter: Callable that formats a node for display
        """
        if not sys.stdin.isatty():
            msg = "Interactive mode requires a real terminal."
            raise RuntimeError(msg)
        self.tree_data_provider = tree_data_provider
        self.node_formatter = node_formatter

        # UI state
        self.expanded_nodes: set[EventKeyT] = (
            set()
        )  # Keys of expanded nodes (instead of collapsed)
        self.current_pos = 0  # Current selected position
        self.scroll_offset = 0  # Vertical scroll offset

    def _render_tree(
        self,
        stdscr: curses.window,
        display_data: list[NodeTerminalUI],
        max_y: int,
        max_x: int,
    ) -> None:
        """Render the tree data on the screen."""
        # Limit display data to visible area
        visible_height = max_y - 4  # Account for header and help

        # Initialize screen position and map of rows that need spacing
        screen_y = 2  # Start after header

        # Calculate visible range accounting for spacers
        visible_end = min(self.scroll_offset + visible_height, len(display_data))

        # Render the visible portion
        for i in range(self.scroll_offset, visible_end):
            node = display_data[i]

            # Calculate screen position
            abs_pos = i

            # Color based on selection
            color = (
                curses.color_pair(2)
                if abs_pos == self.current_pos
                else curses.color_pair(1)
            )

            # Generate prefix based on depth and position
            prefix = get_prefix(node, display_data)

            # Get indicator for expandable nodes
            indicator = ""
            if node["has_children"]:
                indicator = (
                    "[+] "
                    if node["line"].event_key not in self.expanded_nodes
                    else "[-] "
                )

            # Format the node using the provided formatter
            line_text = self.node_formatter(node["line"], indicator)

            # Combine and truncate if needed
            full_line = f"{prefix}{line_text}"
            if len(full_line) >= max_x:
                full_line = full_line[: max_x - 3] + "..."

            # Add to screen
            stdscr.addstr(screen_y, 0, full_line, color)
            screen_y += 1

    def _toggle_collapse(
        self,
        current_node: NodeTerminalUI,
    ) -> None:
        """Toggle collapse state of the current node."""
        node_key = current_node["line"].event_key
        if node_key in self.expanded_nodes:
            self.expanded_nodes.remove(node_key)
        else:
            self.expanded_nodes.add(node_key)

    def run(self) -> None:
        """Run the terminal UI."""
        curses.wrapper(self.main_curses_loop)

    def _clamp_pos(self, display_len: int) -> None:
        if display_len <= 0:
            self.current_pos = 0
            self.scroll_offset = 0
            return
        if self.current_pos >= display_len:
            self.current_pos = display_len - 1
        self.current_pos = max(self.current_pos, 0)

    def _ensure_visible(self, visible_height: int, display_len: int) -> None:
        if display_len <= 0:
            self.scroll_offset = 0
            return

        max_scroll = max(0, display_len - visible_height)
        self.scroll_offset = min(self.scroll_offset, max_scroll)
        self.scroll_offset = max(self.scroll_offset, 0)

        if self.current_pos < self.scroll_offset:
            self.scroll_offset = self.current_pos
        elif self.current_pos >= self.scroll_offset + visible_height:
            self.scroll_offset = self.current_pos - visible_height + 1

    def _move(self, delta: int, display_len: int, visible_height: int) -> None:
        if display_len <= 0:
            return
        self.current_pos = min(max(self.current_pos + delta, 0), display_len - 1)
        self._ensure_visible(visible_height, display_len)

    def _page(self, delta_pages: int, display_len: int, visible_height: int) -> None:
        if display_len <= 0:
            return
        delta = delta_pages * visible_height
        self.current_pos = min(max(self.current_pos + delta, 0), display_len - 1)
        self.scroll_offset = self.scroll_offset + delta
        self._ensure_visible(visible_height, display_len)

    def _dispatch_key(
        self,
        key: int,
        display_data: list[NodeTerminalUI],
        visible_height: int,
    ) -> bool:
        """Dispatch a key event to the UI."""
        if key == ord("q"):
            return False

        display_len = len(display_data)

        def toggle() -> None:
            if 0 <= self.current_pos < display_len:
                node = display_data[self.current_pos]
                if node["has_children"]:
                    self._toggle_collapse(node)

        actions: dict[int, Callable[[], None]] = {
            curses.KEY_UP: lambda: self._move(-1, display_len, visible_height),
            curses.KEY_DOWN: lambda: self._move(1, display_len, visible_height),
            curses.KEY_PPAGE: lambda: self._page(-1, display_len, visible_height),
            curses.KEY_NPAGE: lambda: self._page(1, display_len, visible_height),
            ord("\n"): toggle,
        }

        action = actions.get(key)
        if action is not None:
            action()

        return True

    def main_curses_loop(self, stdscr: curses.window) -> None:
        """Main curses loop for displaying and interacting with the tree."""
        initialise_curses(stdscr)
        root_nodes = self.tree_data_provider(None)

        running = True
        while running:
            # Get terminal dimensions
            max_y, max_x = stdscr.getmaxyx()

            # Adjust scroll_offset if window is resized to be smaller
            visible_height = max_y - 4
            display_data = generate_display_data(
                root_nodes,
                self.expanded_nodes,
                self.tree_data_provider,
            )
            self._clamp_pos(len(display_data))
            self._ensure_visible(visible_height, len(display_data))

            stdscr.clear()
            header = "LINE TRACE TREE"
            stdscr.addstr(0, 0, header, curses.color_pair(3) | curses.A_BOLD)
            stdscr.addstr(1, 0, "=" * len(header), curses.color_pair(3))

            self._render_tree(stdscr, display_data, max_y, max_x)
            stdscr.addstr(max_y - 1, 0, TUI_HELP_TEXT, curses.color_pair(3))
            stdscr.refresh()

            key = stdscr.getch()
            running = self._dispatch_key(key, display_data, visible_height)


def initialise_curses(stdscr: curses.window) -> None:
    """Initialise the curses environment."""
    # Initialize curses
    stdscr.clear()
    curses.curs_set(0)  # Hide cursor
    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Normal text
    curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Highlighted text
    curses.init_pair(3, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Headers

    # Enable keypad and nodelay for better input handling
    stdscr.keypad(True)
    stdscr.nodelay(False)  # Block and wait for input
