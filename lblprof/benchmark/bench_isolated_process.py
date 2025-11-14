"""This script is run in an isolated process to benchmark the overhead of lblprof.
It takes as arguments the module name, function name, and mode (profiled or unprofiled)"""

if __name__ == "__main__":
    import sys
    import time
    import json
    import importlib

    # args: module function mode
    module, func_name, mode = sys.argv[1], sys.argv[2], sys.argv[3]

    mod = importlib.import_module(module)
    fn = getattr(mod, func_name)

    start = time.perf_counter()
    if mode == "profiled":
        from lblprof import start_monitoring, stop_monitoring

        start_monitoring()
        fn()
        stop_monitoring()
    else:
        fn()
    end = time.perf_counter()

    print(json.dumps({"time": end - start}))
