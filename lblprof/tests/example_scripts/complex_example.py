import math
import time
import random
from functools import lru_cache


class Calculator:
    def __init__(self):
        self.values = []

    def compute_square_roots(self, numbers):
        return [math.sqrt(n) for n in numbers]

    def simulate_workload(self):
        for _ in range(3):
            time.sleep(0.05)
            self.values.append(random.randint(1, 100))


@lru_cache(maxsize=None)
def recursive_fib(n):
    if n <= 1:
        return n
    return recursive_fib(n - 1) + recursive_fib(n - 2)


def generate_data(size):
    return [random.randint(1, 1000) for _ in range(size)]


def main():
    calc = Calculator()
    time.sleep(0.2)
    data = generate_data(5)
    calc.compute_square_roots(data)
    calc.simulate_workload()

    for i in range(10):
        recursive_fib(i)


main()
