import time

def outer():
    time.sleep(0.1)
    def inner():
        time.sleep(0.1)
    inner()

if __name__ == "__main__":
    outer() 