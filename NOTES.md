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

## D05 - CI/CD and going live

- Live URL: https://patentpath.onrender.com
- CI PR #4: https://github.com/anushreeee2006-star/prince28-law08-patentpath/pull/4
- Automatic CD run: https://github.com/anushreeee2006-star/prince28-law08-patentpath/actions/runs/44716472392

### Rollback drill
- Rolled back to SHA: 3442b86d0b302dbe702b4f52b3ef0696991fe44e
- Rollback smoke test: Passed
- /health: HTTP 200
- /ready: HTTP 200, database ready
- /v1/documents?limit=1: HTTP 200

### Roll-forward
- Restored SHA: 719bf45c8684796e9a2283b9e792f1af8dbaa0cb
- Final smoke test: Passed
- /health: HTTP 200
- /ready: HTTP 200, database ready
- /v1/documents?limit=1: HTTP 200

### Monitoring
- UptimeRobot monitors /health every 5 minutes.
- Email alerts enabled.
- HEAD requests supported by /health.
- Monitor status verified Up.

### Secrets
- DATABASE_URL stored in GitHub Actions Secrets and Render environment.
- RENDER_DEPLOY_HOOK stored in GitHub Actions Secrets.
- No secrets committed to Git.
