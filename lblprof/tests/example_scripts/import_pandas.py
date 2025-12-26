import logging
import time


def main():
    start = time.perf_counter()
    import pandas as pd  # noqa: F401, PLC0415

    end = time.perf_counter()
    logging.info(f"Time taken to import pandas: {end - start} seconds")


main()
