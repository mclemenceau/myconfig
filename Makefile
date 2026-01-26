VENV := .venv
PY   := $(VENV)/bin/python3
PIP  := $(VENV)/bin/pip3

.PHONY: all deps bootstrap lint test clean

$(VENV):
	python3 -m venv $(VENV)

deps: $(VENV)
	$(PIP) install -e ".[dev]"

bootstrap: deps

# Development workflow

lint: deps
	$(VENV)/bin/ruff check src/myconfig tests

test: deps
	$(PY) -m pytest -q

clean:
	rm -rf $(VENV)
