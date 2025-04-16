import time


def main():
    time.sleep(1)
    start = time.perf_counter()
    import pandas as pd  # noqa: F401

    end = time.perf_counter()
    print(f"Time taken to import pandas: {end - start} seconds")
    return


if __name__ == "__main__":
    main()
