# PatentPath

## Project Overview

PatentPath helps users understand Indian patent basics, including patentability, provisional vs complete filing, fees and forms.

## User Scenario

A final-year ECE student at Prince College has built a low-cost IoT irrigation sensor and wants to file a provisional patent. PatentPath explains patentability, Section 3 exclusions, filing steps and applicable fee categories.

## Data Sources

- Patents Act, 1970
- Patents Rules, 2003 (as amended)
- Manual of Patent Office Practice and Procedure
- Guidelines for Computer-Related Inventions
- Patent Office fee schedule
- Sample granted patent specifications

## Tech Stack

- Python 3.12, FastAPI
- PostgreSQL, SQLAlchemy, Alembic
- Redis, Docker Compose
- pytest, pytest-cov, Ruff
- Poe the Poet

## Prerequisites

- Python 3.12+
- uv
- Docker Desktop with Docker Compose

## Local Development

Install dependencies: `uv sync --locked`

Start API: `uv run poe dev`

## Docker Compose

Start services: `docker compose up --build -d`

Run migrations: `uv run poe migrate`

Load sample data: `uv run poe seed`

Stop services: `docker compose down`

## Quality Checks

- Lint: `uv run poe lint`
- Unit tests: `uv run poe test`
- All tests: `uv run poe test-all`
- Coverage: `uv run poe cov`
- Integration tests: `uv run poe test-integration`

Integration tests use `TEST_DATABASE_URL`. Default local URL:

`postgresql://app:app@localhost:5433/app_test` <!-- pragma: allowlist secret -->

## Docker Test Environment

Build: `docker build -f Dockerfile.test -t patentpath-test .`

Run integration tests:

`docker run --rm --network patentpath_default -e TEST_DATABASE_URL="postgresql://app:app@db:5432/app_test" patentpath-test` <!-- pragma: allowlist secret -->

Run unit tests:

`docker run --rm patentpath-test pytest tests/unit -v`

Run coverage:

`docker run --rm --network patentpath_default -e TEST_DATABASE_URL="postgresql://app:app@db:5432/app_test" patentpath-test pytest --cov --cov-report=term-missing` <!-- pragma: allowlist secret -->

## Current Testing Results

- Unit tests: 16 passed
- Integration tests: 7 passed
- Total: 23 passed
- Test coverage: 91%

## Target Metric

Section 3 flags should agree with a reviewer on at least 80% of 20 invention scenarios.

## Current Progress

FastAPI application skeleton, PostgreSQL persistence, Docker Compose services, migrations, database loading, unit tests and integration tests are implemented.
