.PHONY: lint ci-lint lint-ruff lint-ty test test-db-up test-db-down help

# Default target
all: lint

# Package directory
PKG_DIR := ./mountaineer_billing/
RUFF_PATHS := mountaineer_billing scripts
TEST_COMPOSE_FILE := docker-compose.test.yml

# Define a function to run ruff on the billing source tree
# Usage: $(call run_ruff,<paths>)
define run_ruff
	@echo "\n=== Running ruff on $(1) ==="; \
	echo "Running ruff format in $(1)"; \
	uv run ruff format $(1) || { echo "FAILED: ruff format in $(1)"; exit 1; }; \
	echo "Running ruff check --fix in $(1)"; \
	uv run ruff check --fix $(1) || { echo "FAILED: ruff check in $(1)"; exit 1; }; \
	echo "=== ruff completed successfully for $(1) ===";
endef

# Define a function to run ruff in CI mode (check only, no fixes)
# Usage: $(call run_ruff_ci,<paths>)
define run_ruff_ci
	@echo "\n=== Running ruff (validation only) on $(1) ==="; \
	echo "Running ruff format --check in $(1)"; \
	uv run ruff format --check $(1) || { echo "FAILED: ruff format in $(1)"; exit 1; }; \
	echo "Running ruff check (no fix) in $(1)"; \
	uv run ruff check $(1) || { echo "FAILED: ruff check in $(1)"; exit 1; }; \
	echo "=== ruff validation completed successfully for $(1) ===";
endef

# Define a function to run ty on the package source tree.
# The generated Stripe models and test suite are excluded because ty produces
# low-signal diagnostics there today.
# Usage: $(call run_ty,<directory>)
define run_ty
	@echo "\n=== Running ty on $(1) ==="; \
	uv run ty check --project . --exclude 'mountaineer_billing/stripe/**' --exclude 'mountaineer_billing/__tests__/**' $(1) || { echo "FAILED: ty in $(1)"; exit 1; }; \
	echo "=== ty completed successfully for $(1) ===";
endef

# Main lint target (with fixes)
lint:
	@echo "=== Linting mountaineer-billing ==="
	$(call run_ruff,$(RUFF_PATHS))
	$(call run_ty,$(PKG_DIR))
	@echo "\n=== All linters completed successfully ==="

# CI lint target (validation only, no fixes)
ci-lint:
	@echo "=== CI Linting mountaineer-billing (validation only) ==="
	$(call run_ruff_ci,$(RUFF_PATHS))
	$(call run_ty,$(PKG_DIR))
	@echo "\n=== All linters completed successfully ==="

# Tool-specific targets
lint-ruff:
	@echo "=== Running ruff ==="
	$(call run_ruff,$(RUFF_PATHS))

lint-ty:
	@echo "=== Running ty ==="
	$(call run_ty,$(PKG_DIR))

# Test target
test:
	@set -e; \
	cleanup() { docker compose -f $(TEST_COMPOSE_FILE) down -v --remove-orphans >/dev/null 2>&1 || true; }; \
	trap cleanup EXIT; \
	echo "=== Starting test database ==="; \
	docker compose -f $(TEST_COMPOSE_FILE) up -d --wait; \
	echo "=== Running tests ==="; \
	uv run pytest -vvv $(PKG_DIR)
	@echo "=== Tests completed successfully ==="

test-db-up:
	@echo "=== Starting test database ==="
	docker compose -f $(TEST_COMPOSE_FILE) up -d --wait
	@echo "=== Test database ready ==="

test-db-down:
	@echo "=== Stopping test database ==="
	docker compose -f $(TEST_COMPOSE_FILE) down -v --remove-orphans
	@echo "=== Test database stopped ==="

# Show help
help:
	@echo "Available targets:"
	@echo " "
	@echo "  lint            - Run all linters (with fixes)"
	@echo "  ci-lint         - Run all linters (validation only)"
	@echo "  lint-ruff       - Run Ruff only (with fixes)"
	@echo "  lint-ty         - Run ty type checker only"
	@echo " "
	@echo "  test            - Start the test database, run tests, then tear it down"
	@echo "  test-db-up      - Start the Postgres test database"
	@echo "  test-db-down    - Stop and remove the Postgres test database"
