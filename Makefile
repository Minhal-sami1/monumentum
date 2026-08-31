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

.PHONY: setup check-schemas conformance demo scenarios adversarial reproduce paper \
        reproduce-check quickstart-test verify-self test lint verify

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

reproduce:
	bash experiments/reproduce.sh "$(PYTHON)" $(REPRODUCE_ARGS)

paper: reproduce-check
	bash paper/build.sh "$(PYTHON)"

# fail early if the paper is asked to build without generated metrics
reproduce-check:
	@test -f paper/figures/metrics.tex || ( echo "run 'make reproduce' first"; exit 1 )

quickstart-test:
	bash docs/quickstart_test.sh "$(PYTHON)"

verify-self:
	$(PYTHON) -m agentloop.cli verify .

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests conformance sdk demo skill experiments paper

# verify grows with the milestones. m7 final gate: everything that must be
# green in a fresh CI clone (no live model, no paper build).
verify: check-schemas conformance test demo scenarios adversarial quickstart-test verify-self lint
