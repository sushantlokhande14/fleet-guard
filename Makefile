# Common tasks. Everything runs in Docker except the web dev server.

COMPOSE ?= docker compose
RUN     := $(COMPOSE) run --rm migrate

.PHONY: help up down logs smoke core test-core test-py test-web lint dashboards campaign benchmark scale

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-12s %s\n", $$1, $$2}'

up: ## build and start the whole stack (UI :8080, API :8000, Grafana :3000)
	$(COMPOSE) up -d --build --wait api web worker
	$(COMPOSE) up -d prometheus alertmanager grafana

down: ## stop the stack (data volumes are kept)
	$(COMPOSE) down

logs: ## follow api and worker logs
	$(COMPOSE) logs -f api worker

smoke: ## end-to-end smoke test against the running stack
	python3 tools/e2e_smoke.py

core: ## build fgsim and run the C++ tests in the toolchain image
	docker build --target core .

test-core: core ## alias for core

test-py: ## Python tests in the dev image (needs a reachable Postgres in FG_TEST_DATABASE_URL)
	docker build --target dev -t fleetguard-dev .
	docker run --rm --network host -e FG_TEST_DATABASE_URL -v "$(PWD)/tests:/src/tests" -w /src fleetguard-dev pytest -q

test-web: ## UI typecheck and tests
	cd web && npm ci && npm run typecheck && npm test

lint:
	ruff check fleetguard tests tools

dashboards: ## regenerate the provisioned Grafana dashboards
	python3 tools/gen_dashboards.py

campaign: ## queue rc1 against the baseline (700 scenarios)
	$(RUN) fleetguard campaign create --baseline drive-2.3.0 --candidate drive-2.4.0-rc1 --count 700

benchmark: ## seeded-regression benchmark into docs/benchmark
	$(COMPOSE) run --rm -v "$(PWD)/docs:/app/docs" migrate fleetguard benchmark --out /app/docs/benchmark

scale: ## one 100,000-drive campaign
	$(RUN) fleetguard campaign create --baseline drive-2.3.0 --candidate drive-2.4.0-rc1 --count 50000 \
		--seed-start 100000 --run
