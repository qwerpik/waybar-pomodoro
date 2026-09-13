.PHONY: test lint typecheck check install uninstall clean build

PYTHON ?= python3
PREFIX ?= $(HOME)/.local

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

lint:
	ruff check .
	ruff format --check .

typecheck:
	mypy src

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
