.PHONY: help run run-prod migrate worker test test-cov-xml lint lint-check \
        translations-add translations-update translations-compile \
        static-build migrations-create migrations-migrate \
        dev-env-start dev-env-stop dev-server-start dev-worker-start dev-server-watch dev-worker-watch

## Help: List all available commands.
help:
	@echo "Available commands:"
	@grep -E '^[a-zA-Z0-9_-]+:' $(MAKEFILE_LIST) | sed -e 's/:.*$$//' | sort | uniq | awk '{printf "  %-25s\n", $$1}'

#########################
# Application Commands
#########################

# run: Run the FastAPI application with auto‑reload.
run:
	uvicorn auth.app:app --host 0.0.0.0 --port 8000 --reload

# run-prod: Run the FastAPI application without auto‑reload (production).
run-prod:
	uvicorn auth.app:app --host 0.0.0.0 --port 8000

# migrate: Run database migrations.
migrate:
	python -m auth.cli migrate

# worker: Run the Dramatiq worker.
worker:
	dramatiq auth.worker -p 1 -t 1 -f auth.scheduler:schedule

#########################
# Makefile Commands
#########################

# Test: Run tests with pytest.
test:
	pytest {args}

# Test Coverage XML: Run tests with coverage report in XML format.
test-cov-xml:
	pytest --cov auth/ --cov-report=xml --exitfirst

# Lint: Format code, check for issues, and run mypy.
lint:
	ruff format . && ruff check --fix . && mypy auth/

# Lint Check: Check code formatting and issues without fixing.
lint-check:
	ruff format --check . && ruff check . && mypy auth/

# Translations Add: Create new translation files.
translations-add:
	mkdir -p auth/locale/{args}/LC_MESSAGES && touch auth/locale/{args}/LC_MESSAGES/messages.po && translations-update

# Translations Update: Update translation files.
translations-update:
	pybabel extract --mapping babel.cfg --output-file=auth/locale/messages.pot . && pybabel update --domain=messages --input-file=auth/locale/messages.pot --output-dir=auth/locale

# Translations Compile: Compile translation files.
translations-compile:
	pybabel compile --domain=messages --directory=auth/locale

# Static Build: Build static assets.
static-build:
	npm run build

# Migrations Create: Create a new migration.
migrations-create:
	docker compose up -d db && env GENERATE_MIGRATION=1 alembic -c auth/alembic.ini revision --autogenerate -m {args}

# Migrations Migrate: Apply migrations.
migrations-migrate:
	docker compose up -d db && env GENERATE_MIGRATION=1 alembic -c auth/alembic.ini upgrade head

# Telemetry Set Posthog Key: Set the Posthog API key in the service file.
telemetry-set-posthog-key:
	sed -i.bak 's/__POSTHOG_API_KEY__/{args}/' auth/services/posthog.py && rm auth/services/posthog.py.bak

# Development Environment Start: Start the development environment.
dev-env-start:
	docker compose up -d

# Development Environment Stop: Stop the development environment.
dev-env-stop:
	docker compose stop

# Development Server Start: Start the development server.
dev-server-setup:
	make translations-compile && make static-build

# Development Server Watch: Watch for changes and restart the development server.
dev-server-watch:
	watchfiles --ignore-paths auth/static,auth/locale 'dev-server-start' auth js styles

# Development Worker Watch: Watch for changes and restart the development worker.
dev-worker-watch:
	watchfiles --ignore-paths auth/static,auth/locale 'dev-worker-start' auth
