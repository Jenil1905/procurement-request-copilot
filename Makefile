.PHONY: help start eval test public-eval clean

SHELL := /bin/bash
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

help:
	@echo "AI Procurement Request Copilot - Commands:"
	@echo "  make start        Create venv, install deps, start mock service & web app"
	@echo "  make eval         Run evaluation benchmark across Arch A and Arch B"
	@echo "  make test         Run pytest unit and integration test suite"
	@echo "  make public-eval  Run starter pack public verification tests"
	@echo "  make clean        Remove cache files and temporary test artifacts"

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@if [ ! -f .env ]; then cp .env.example .env; fi

start: $(VENV)/bin/activate
	$(PYTHON) run_local.py

eval: $(VENV)/bin/activate
	$(PYTHON) eval/run_eval.py --arch both

test: $(VENV)/bin/activate
	$(PYTHON) -m pytest tests/ -v

public-eval: $(VENV)/bin/activate
	$(PYTHON) evals/run_public_evals.py --architecture single
	$(PYTHON) evals/run_public_evals.py --architecture staged

clean:
	rm -rf __pycache__ src/__pycache__ tests/__pycache__ eval/__pycache__ mock_api/__pycache__
	rm -rf .pytest_cache
