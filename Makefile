# agentloop build entry points. Every milestone gate is a target here.
# Cross-platform: venv layout differs between POSIX and Windows.

VENV := .venv
ifeq ($(OS),Windows_NT)
BIN := $(VENV)/Scripts
else
BIN := $(VENV)/bin
endif
PY ?= python
PYTHON := $(BIN)/python

.PHONY: setup check-schemas conformance test lint verify

setup:
	$(PY) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

check-schemas:
	$(PYTHON) -m agentloop.cli check-schemas --golden conformance/golden

conformance:
	$(PYTHON) conformance/runner.py --executor "$(PYTHON) -m agentloop.cli"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests conformance

# verify grows with the milestones. m2: schemas + conformance + unit tests + lint.
verify: check-schemas conformance test lint
