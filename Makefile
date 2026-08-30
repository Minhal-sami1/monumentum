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

.PHONY: setup check-schemas test lint verify

setup:
	$(PY) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

check-schemas:
	$(PYTHON) -m agentloop.cli check-schemas --golden conformance/golden

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

# verify grows with the milestones. m1: schemas + unit tests + lint.
verify: check-schemas test lint
