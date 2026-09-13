.PHONY: test install uninstall clean

PYTHON ?= python3
PREFIX ?= $(HOME)/.local

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

install:
	./install.sh

uninstall:
	./uninstall.sh

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete
	rm -rf build dist *.egg-info .pytest_cache
