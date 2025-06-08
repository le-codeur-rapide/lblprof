def doublezip():
    rows = [(1, 2, None), (3, 4, None), (5, 6, None), (7, 8, None)]
    _ = list(zip(*[col for col in zip(*rows) if any(cell is not None for cell in col)]))
    _ = any(cell is not None for cell in rows[0])


if __name__ == "__main__":
    doublezip()
