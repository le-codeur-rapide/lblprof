import time


def generator():
    for i in range(10):
        time.sleep(0.05)
        yield i


for i in generator():
    print(i)

gene = list(generator())

pure_gene = list(time.sleep(0.1) for i in range(10))

double_gen = list(time.sleep(0.1) for i in range(2) for j in range(2) if True)

# rows = [(1, 2, None), (3, 4, None), (5, 6, None)]
# filtered = list(
#     zip(*[
#         col for col in zip(*rows)
#         if any(cell is not None for cell in col)
#     ])
# )
