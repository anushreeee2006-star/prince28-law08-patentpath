## D04 - Compose Health and Recovery Evidence

### Migration
- First run: records=20 inserted=20 updated=0 unchanged=0
- Second run: records=20 inserted=0 updated=0 unchanged=20

### API Health Checks
- DB running: /health -> {"status":"ok"}
- DB running: /ready -> {"status":"ready","checks":{"database":true}}

### Database Failure and Recovery
- DB stopped successfully.
- /health while DB stopped: {"status":"ok"}
- /ready while DB stopped: {"status":"not_ready","checks":{"database":false}}
- DB restarted successfully.
- /ready after restart: {"status":"ready","checks":{"database":true}}

## D04 - Task runner, Docker and test evidence

### Docker image
- Image: patentpath:dev
- Disk usage: 300 MB (target: under 400 MB)
- Content size: 70 MB
- Runtime user: uid=999(app) gid=999(app) groups=999(app)
- First build time: 41.6 seconds (previously recorded)
- Incremental build after a one-line change: not measured in this run.
- Build cache: Docker reused unchanged cached layers, avoiding rebuilding those steps.

### Compose stack and migration
- API: Up and healthy
- PostgreSQL: Up and healthy
- Redis: Up and healthy
- Migration: Exited (0)
- First seed: records=20 inserted=20 updated=0 unchanged=0
- Subsequent seed: records=20 inserted=0 updated=0 unchanged=20

### Tests and coverage
- Unit tests: 16 passed
- Integration tests: 7 passed
- Combined: 23 passed
- Unit-only coverage TOTAL: 80%
- Unit + integration coverage TOTAL: 92%

### Uncovered code review
- middleware.py lines 25-34: exception logging path; not reached by normal successful requests, but important for logging unexpected request failures.
- repository.py lines 33, 36-37 and 67: boolean/decimal filter conversion and invalid-filter handling; edge cases that remain useful for robust filter validation.

### Windows test execution note
- The Windows Application Control policy blocked the Poe executable.
- Tests and coverage were therefore run successfully through isolated uv environments using pytest directly.
