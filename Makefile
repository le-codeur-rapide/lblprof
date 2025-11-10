
# Default target
.PHONY: all
all: lint test

install:
	uv venv && uv pip install -e .

test:
	uv run pytest

lint:
	uv run ruff check . --fix