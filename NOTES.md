# Engineering Notes: PatentPath

## D03 - PostgreSQL

### Migrations

- Downgrade: `1190a664399b` -> `9422b52fab0b`
- Upgrade head: `9422b52fab0b` -> `1190a664399b`
- Final migration: `1190a664399b` (head)

Migration history:

- `9422b52fab0b` -> `1190a664399b`: add GIN index on metadata
- `<base>` -> `9422b52fab0b`: create documents and pages tables

### Loader idempotency

- Run 1: records=20, inserted=0, updated=0, unchanged=20
- Run 2: records=20, inserted=0, updated=0, unchanged=20
- Run 3: not performed; sample data was not modified

### EXPLAIN for section filters 7, 54, 135

- Planner selected sequential scan.
- With sequential scan disabled, PostgreSQL selected a bitmap heap scan using `ix_documents_metadata_gin`.
- Sequential scan was faster for the small 20-row table.

The planner may choose the GIN index when the table grows and index access becomes cheaper.

## D04 - Docker Build Cache

- Initial build: 26.9 seconds
- Second build after changing the `/health` docstring: 32.5 seconds
- Dependency layer `uv sync --locked --no-install-project` was cached.
- Non-root verification: `uid=999(app) gid=999(app) groups=999(app)`.
- Original `/health` docstring was restored after the cache test.

## D04 - Testing

- Unit tests: 16 passed.
- Integration tests: 7 passed.
- Total: 23 passed.
- Overall test coverage: 91%.
- Integration tests ran against the PostgreSQL `app_test` database in Docker.
- Windows Application Control blocked some local Python executables and native extensions, so tests were executed successfully in a Linux Docker test image.

## D04 - Task Runner

Configured Poe tasks:

- `dev`
- `lint`
- `test`
- `test-all`
- `test-integration`
- `cov`
- `migrate`
- `seed`

## D04 - Verification Notes

- Poe task definitions are present in `pyproject.toml`.
- Running `uv run poe --help` on Windows was blocked by Windows Application Control (os error 4551).
- Docker clean-clone verification is pending because the C: drive has no free space and Docker Desktop cannot start its engine.
- The existing Docker database volume has been preserved; no volume cleanup was performed.
