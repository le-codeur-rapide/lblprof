# See https://github.com/le-codeur-rapide/lblprof/issues/5 for context

import time
from lblprof import start_monitoring, stop_monitoring, tracer


def test_tracing_no_new_context():
    start_monitoring()
    time.sleep(0.1)
    stop_monitoring()
    # check that the time.sleep is in the tree
    line_codes = [line.source for line in tracer.tree.root_lines]
    assert "time.sleep(0.1)" in line_codes
