import time


def outer():
    time.sleep(0.05)

    def inner():
        time.sleep(0.05)

    inner()


if __name__ == "__main__":
    outer()
