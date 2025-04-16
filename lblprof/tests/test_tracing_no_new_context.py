# See https://github.com/le-codeur-rapide/lblprof/issues/5 for context

import time
from lblprof import set_custom_trace, stop_custom_trace, tracer


def test_tracing_no_new_context():
    set_custom_trace()
    time.sleep(0.1)
    stop_custom_trace()
    # check that the time.sleep is in the tree
    line_codes = [line.source for line in tracer.tree.lines.values()]
    assert "time.sleep(0.1)" in line_codes
