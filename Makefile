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

.PHONY: setup check-schemas conformance demo scenarios adversarial verify-self test lint verify

setup:
	$(PY) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]" -e ./sdk

check-schemas:
	$(PYTHON) -m agentloop.cli check-schemas --golden conformance/golden

conformance:
	$(PYTHON) conformance/runner.py --executor "$(PYTHON) -m agentloop.cli"

demo:
	$(PYTHON) demo/run_demo.py

scenarios:
	bash scenarios/run_all.sh "$(PYTHON)"

adversarial:
	bash adversarial/run_all.sh "$(PYTHON)"

verify-self:
	$(PYTHON) -m agentloop.cli verify .

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests conformance sdk demo skill

# verify grows with the milestones. m6: + adversarial.
verify: check-schemas conformance test demo scenarios adversarial verify-self lint
