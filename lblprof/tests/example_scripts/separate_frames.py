import time

# from lblprof import start_monitoring, stop_tracing, show_tree
import logging

logging.basicConfig(level=logging.DEBUG)


def main():
    time.sleep(0.01)
    main2()


def main2():
    time.sleep(0.01)
    # stop_tracing()
    time.sleep(0.01)


# start_monitoring()
main()
time.sleep(0.01)

# show_tree()
