SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PREFIX ?= $(HOME)/bin
VAULT ?=

# --- help ---

.PHONY: help
help: ## List every target with its description
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# --- development ---

.PHONY: sync
sync: ## Create the virtualenv (system GI bindings visible) and install dependencies
	@test -d .venv || uv venv --python /usr/bin/python3 --system-site-packages
	@uv sync

.PHONY: check
check: ## Everything a commit has to pass: ruff and the test suite
	@uv run ruff check .
	@uv run pytest -q

.PHONY: test
test: ## Run the test suite only
	@uv run pytest -q

.PHONY: lint
lint: ## Run ruff only
	@uv run ruff check .

.PHONY: run
run: ## Run from the working tree; make run VAULT=~/path/to/vault opens it
	@uv run python -m obsidian_reader.cli $(VAULT)

.PHONY: smoke
smoke: ## Drive the real window through open, render, and search on the live display
	@tmp=$$(mktemp -d) && printf '# A\n\n[[Second Note]]\n\nAn #alpha tag and math $$e=mc^2$$ inline.\n\n> [!note]\n> callout\n' > "$$tmp/A.md" && printf '# B\n' > "$$tmp/Second Note.md" && printf '{"nodes":[{"id":"a","type":"text","x":0,"y":0,"width":100,"height":40,"text":"hi"},{"id":"b","type":"file","x":200,"y":0,"width":100,"height":40,"file":"A.md"}],"edges":[{"id":"e","fromNode":"a","toNode":"b"}]}' > "$$tmp/Board.canvas" && mkdir "$$tmp/.obsidian" && printf '{"items":[{"type":"file","path":"A.md"}]}' > "$$tmp/.obsidian/bookmarks.json" && XDG_CONFIG_HOME="$$tmp/config" XDG_CACHE_HOME="$$tmp/cache" uv run python scripts/gui-smoke.py "$$tmp"; rm -rf "$$tmp"

# --- install ---

.PHONY: install
install: ## Install the launcher to PREFIX (default ~/bin) plus desktop entry and icon
	@scripts/install.sh $(PREFIX)

.PHONY: uninstall
uninstall: ## Remove what install placed
	@scripts/uninstall.sh $(PREFIX)

# --- housekeeping ---

.PHONY: clean
clean: ## Remove caches and build products; the virtualenv stays
	@rm -rf .pytest_cache .ruff_cache dist build src/*.egg-info
