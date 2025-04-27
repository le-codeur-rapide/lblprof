import time


def main():
    time.sleep(0.1)
    try:
        time.sleep(0.1)
        raise Exception("test")
    except Exception:
        time.sleep(0.1)
    finally:
        time.sleep(0.1)
    time.sleep(0.1)
    return


if __name__ == "__main__":
    main()
