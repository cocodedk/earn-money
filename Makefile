.PHONY: smoke lint test fmt install-dev clean

PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin

$(VENV_BIN)/python:
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip

install-dev: $(VENV_BIN)/python
	$(VENV_BIN)/pip install -e ".[dev]"

lint: install-dev
	$(VENV_BIN)/ruff check src tests
	$(VENV_BIN)/mypy src

test: install-dev
	$(VENV_BIN)/pytest

fmt: install-dev
	$(VENV_BIN)/ruff format src tests
	$(VENV_BIN)/ruff check --fix src tests

smoke: lint test

clean:
	rm -rf $(VENV) build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
