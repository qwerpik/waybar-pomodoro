.PHONY: test lint typecheck check install uninstall clean build

PYTHON ?= python3
PREFIX ?= $(HOME)/.local

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

lint:
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check . && ruff format --check .; \
	elif command -v uv >/dev/null 2>&1; then \
		uv run --with ruff ruff check . && uv run --with ruff ruff format --check .; \
	else \
		echo "ruff not found, install ruff or uv"; exit 1; \
	fi

typecheck:
	@if command -v mypy >/dev/null 2>&1; then \
		mypy src; \
	elif command -v uv >/dev/null 2>&1; then \
		uv run --with mypy mypy src; \
	else \
		echo "mypy not found, install mypy or uv"; exit 1; \
	fi

check: lint typecheck test

build:
	$(PYTHON) -m build

install:
	PREFIX="$(PREFIX)" ./install.sh

uninstall:
	PREFIX="$(PREFIX)" ./uninstall.sh

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
