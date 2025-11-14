import time


def fib_iterative(n):
    if n < 0:
        raise ValueError("Input must be a non-negative integer.")
    a, b = 0, 1
    for _ in range(n):
        time.sleep(0.05)
        a, b = b, a + b
    return a


time.sleep(0.05)
fib_iterative(4)
