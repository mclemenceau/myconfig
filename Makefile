VENV := .venv
PY   := $(VENV)/bin/python3

.PHONY: all deps bootstrap lint test clean

all: lint test

# Depend on the interpreter rather than the directory, so a broken or
# stale venv (e.g. after a Python upgrade) gets recreated.
$(PY): pyproject.toml
	rm -rf $(VENV)
	python3 -m venv $(VENV)
	$(PY) -m pip install -e ".[dev]"

deps: $(PY)

bootstrap: deps

# Development workflow

lint: deps
	$(VENV)/bin/ruff check src tests

test: deps
	$(PY) -m pytest -q

clean:
	rm -rf $(VENV) build htmlcov .coverage .pytest_cache .ruff_cache \
		src/*.egg-info
