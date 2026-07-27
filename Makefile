IMAGE_NAME ?= ghcr.io/willysamz/epson-projector-proxy
IMAGE_TAG ?= $(shell cat VERSION)

.PHONY: help install dev run lint lint-fix test test-cov build push version helm-lint helm-template clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-15s %s\n",$$1,$$2}'
install: ## Create venv + install deps
	python -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r requirements.txt
dev: ## Run with autoreload
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
run: ## Run
	.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
lint: ## Lint + typecheck
	.venv/bin/ruff check app/ && .venv/bin/ruff format --check app/ && .venv/bin/mypy app/ --ignore-missing-imports
lint-fix: ## Autofix
	.venv/bin/ruff check --fix app/ && .venv/bin/ruff format app/
test: ## Run tests
	.venv/bin/pytest tests/ -v
test-cov: ## Coverage
	.venv/bin/pytest tests/ -v --cov=app --cov-report=html
build: ## Build image
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .
push: ## Push image
	docker push $(IMAGE_NAME):$(IMAGE_TAG)
version: ## Print version
	@cat VERSION
helm-lint: ## helm lint
	helm lint ./chart
helm-template: ## helm template
	helm template epson ./chart
clean: ## Remove caches
	rm -rf .venv .pytest_cache .mypy_cache .ruff_cache htmlcov app/__pycache__ tests/__pycache__
