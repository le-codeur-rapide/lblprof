# See https://github.com/le-codeur-rapide/lblprof/issues/5 for context

import time

from lblprof import LineStatsTree, start_monitoring, stop_monitoring, tracer


def test_tracing_no_new_context():
    start_monitoring()
    time.sleep(0.01)
    stop_monitoring()
    # We need to build the tree before checking the content
    tree = LineStatsTree(tracer.events)
    tree.build_tree()

    # check that the time.sleep is in the tree
    line_codes = [line.source for line in tree.root_lines]
    assert "time.sleep(0.01)" in line_codes
