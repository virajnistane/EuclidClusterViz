# ClusterViz command menu. All logic lives in setup_venv.sh and launch.sh; these
# targets only call them. Run "make" or "make help" for the list.
#
# Pass extra arguments with ARGS, e.g. make run ARGS="--config my.ini"

.DEFAULT_GOAL := help
.PHONY: help venv setup setup-dev rebuild run run-debug test docs docs-clean clear-cache clean-venv

PY := .venv/bin/python
DOCS := cluster_visualization/docs

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

venv: ## Sync .venv only if uv.lock/pyproject.toml changed
	./setup_venv.sh --if-stale

setup: ## Create or update .venv (installs uv if needed)
	./setup_venv.sh

setup-dev: ## Same, plus dev tools (pytest, black, mypy, ...)
	./setup_venv.sh --dev

rebuild: ## Delete .venv and rebuild it from scratch (keeps installed extras)
	./setup_venv.sh --recreate

run: ## Launch the app (re-syncs .venv first if outdated)
	./launch.sh $(ARGS)

run-debug: ## Launch the app in Dash debug mode
	./launch.sh --debug $(ARGS)

test: ## Run the test suite (adds the dev extra once)
	./setup_venv.sh --if-stale --dev
	$(PY) -m pytest -q cluster_visualization/tests $(ARGS)

docs: ## Build the Sphinx HTML docs into cluster_visualization/docs/_build/html
	./setup_venv.sh --if-stale --docs
	$(PY) -m sphinx -M html $(DOCS) $(DOCS)/_build $(ARGS)

docs-clean: ## Delete the built docs
	rm -rf $(DOCS)/_build

clear-cache: ## Delete the on-disk caches (~/.cache/clusterviz*)
	./launch.sh --clear-cache

clean-venv: ## Delete .venv
	rm -rf .venv
