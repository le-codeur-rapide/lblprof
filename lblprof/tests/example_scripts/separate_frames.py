import time

# from lblprof import start_monitoring, stop_tracing, show_tree
import logging

logging.basicConfig(level=logging.DEBUG)


def main():
    time.sleep(0.1)
    main2()


def main2():
    time.sleep(0.1)
    # stop_tracing()
    time.sleep(0.1)


if __name__ == "__main__":
    # start_monitoring()
    main()
    time.sleep(0.1)

    # show_tree()
