from lblprof.line_stat_object import LineStats


def group_children_by_file(
    children: list[LineStats],
) -> dict[str, list[LineStats]]:
    """Return a dictionary of children grouped by file name and sorted by
    line number:
    dict[file_name: list[children]]"""
    children_by_file: dict[str, list[LineStats]] = {}
    for child in children:
        if child.file_name not in children_by_file:
            children_by_file[child.file_name] = []
        children_by_file[child.file_name].append(child)

    # Sort each file's lines by line number
    for child in children_by_file.values():
        child.sort(key=lambda x: x.line_no)

    return children_by_file


def get_sorted_children(
    children: list[LineStats],
) -> list[LineStats]:
    """Sort children by file and line number.
    Returns a list of children sorted by file name and line number."""
    children_by_file = group_children_by_file(children)
    # Flatten all children
    all_children: list[LineStats] = []
    for child in children_by_file.values():
        all_children.extend(child)

    return all_children
