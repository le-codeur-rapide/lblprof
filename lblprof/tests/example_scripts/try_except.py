import time


def main():
    time.sleep(0.01)
    try:
        time.sleep(0.01)
        raise Exception("test")
    except Exception:
        time.sleep(0.01)
    finally:
        time.sleep(0.01)
    time.sleep(0.01)
    return


main()
