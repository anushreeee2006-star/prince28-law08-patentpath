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

### Stretch Tasks

#### Human approval gate
- A human approval gate is worth the delay for high-risk production deployments that need manual review.
- For routine low-risk changes, automated checks help maintain faster delivery.

#### Lead time measurement

Lead time was measured from pull request merge to successful production smoke test on 2026-11-20.

| CD Run | Pull Request | Merge Time (UTC) | Smoke Test Passed (UTC) | Lead Time |
|---|---|---|---|---|
| #5 | #7 | 14:08:45 | 14:10:55 | 2 min 10 sec |
| #6 | #8 | 14:36:24 | 14:38:34 | 2 min 10 sec |
| #7 | #9 | 14:42:30 | 14:44:24 | 1 min 54 sec |

- Average change lead time: 2 min 5 sec (124.67 seconds).
- Slowest step: Smoke test live deployment (26â€“27 seconds).
- All three measured CD runs completed successfully.

## D03 - PostgreSQL EXPLAIN ANALYZE and GIN Index Evidence

### Test setup
- PostgreSQL: pgvector/pgvector:pg17
- Database: app
- Table: documents
- Total documents: 20
- JSONB field tested: form
- Filter value: Form 1
- GIN index: ix_documents_metadata_gin

### 1. Normal query plan
- Planner selected: Sequential Scan (Seq Scan)
- Matching rows: 1
- Rows removed by filter: 19
- Planning time: 8.804 ms
- Execution time: 0.596 ms

PostgreSQL selected a sequential scan because the table is small (20 records), making a full table scan reasonable.

### 2. GIN index usage verification
- Planner selected: Bitmap Heap Scan
- Index scan: Bitmap Index Scan
- Index used: ix_documents_metadata_gin
- Matching rows: 1
- Index searches: 1
- Planning time: 0.076 ms
- Execution time: 0.871 ms

The GIN index was successfully used for the JSONB containment query after sequential scans were disabled in the test session.

### Conclusion
EXPLAIN ANALYZE confirmed the normal planner behavior and verified that the GIN index on the JSONB metadata column can be used successfully.

## D06 - Collecting the corpus

### Source inventory
- `data/sources.csv` contains 10 official IP India document URLs.
- Source types: 9 PDF documents and 1 HTML page.
- All 10 URLs returned HTTP 200 during the source check.
- Form 2 and Form 3 direct GET checks also confirmed valid PDF responses.
- Downloaded all 10 IP India source documents successfully (9 PDFs and 1 HTML page).

### Copyright and reuse
- Checked the IP India Copyright Policy.
- Reproduction is permitted free of charge subject to accurate reproduction and prominent source attribution.
- Third-party material is excluded unless permission is obtained from its copyright holder.
- IP India logos and the National Emblem must not be used without authorisation.
- Gazette publications remain authoritative for Acts, Rules and other official legal texts.

### Robots.txt and access checks
- Checked `https://ipindia.gov.in/robots.txt`.
- The listed disallowed paths are `/admin`, `/api/`, `/search` and `/site-guide/`.
- The 10 document URLs checked do not use those listed paths.
- IPRSearch robots.txt could not be retrieved because the connection was reset. Its crawling and reuse conditions remain unverified; no automated crawling will be attempted until verified.


### IPRSearch access limitation
- Retried both the IPRSearch robots.txt URL and the main website.
- Both attempts returned `ERR_CONNECTION_RESET`.
- Terms, copyright and robots rules could not be verified.
- IPRSearch is excluded from automated downloading until its permissions and access rules can be confirmed.

### Kill, resume and recovery checks

- Initial run: downloaded=10, skipped=0, blocked=0, failed=0.
- Active-download Ctrl+C interruption: verified; Python raised KeyboardInterrupt after task cancellation.
- Post-interruption recovery: downloaded=1, skipped=9, blocked=0, failed=0.
- Final verification: 10 IP India files present and 0 `.part` files.
- Recovery test: temporarily deleted the Form 3 PDF; rerun restored it.
- Existing FastAPI corpus was preserved.

## D06 · Collecting the corpus

- Start target: Act + Rules + Office Manual
- Collected today: 16 files, 451 PDF pages, 7.48 MB (IP India corpus; 7 HTML files also collected)
- Doors used: URL list / Git repository / sitemap / by hand

### Licence check

| Source | Licence or terms, in my words | May I show full text in answers? |
|---|---|---|
| | | |

### robots.txt

- Site: ________. Its robots.txt says (2 lines): ________
- Was anything blocked for my bot? What did I do about it?

### Kill and resume

- Run 1: I pressed Ctrl+C after ___ files
- Run 2: downloaded=___ skipped=___
- Run 3: downloaded=0 skipped=___

### Capacity (from docs/CAPACITY.md)

- Tokens per page, estimated: 396 (estimated from extracted words)
- Full corpus estimate: 1.98 M tokens, 3,960 chunks, embedding about Rs 37.62, vectors 15.47 MiB (5,000-page target)
- The number that surprised me most, and why (2 lines):

### One thing that went wrong today, and how I fixed it

## Stretch 4 - Your crawl, in numbers

- **Files and size by source:** IP India (CGPDTM): 20 downloaded files, 10.561 MB; FastAPI: 1,696 downloaded files, 12.806 MB. Total: 1,716 files and 23.367 MB.
- **Longest collection window:** IP India (CGPDTM), 67 minutes 46 seconds (14:19:24–15:27:10 UTC), compared with FastAPI at 54 seconds (14:06:41–14:07:35 UTC). These durations are calculated from the earliest and latest manifest timestamps per source; they are collection windows, not individual request durations.
- **Retries:** 0 of the 20 IP India records with an attempts field required more than one attempt. The 1,696 FastAPI records do not contain an attempts field, so their retry count cannot be determined from the manifest.
