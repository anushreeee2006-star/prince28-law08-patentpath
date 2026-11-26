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
- Slowest step: Smoke test live deployment (26Ã¢â‚¬â€œ27 seconds).
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

## D06 Â· Collecting the corpus

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

- **Files and size by source:** Historical manifest totals: IP India (CGPDTM): 20 downloaded files, 10.561 MB; FastAPI: 1,696 extracted files, 12.806 MB. Total: 1,716 files and 23.367 MB.

- **Collection windows:** IP India: 67 minutes 46 seconds (14:19:24-15:27:10 UTC); FastAPI: 54 seconds (14:06:41-14:07:35 UTC). These are collection windows calculated from manifest timestamps, not individual request durations.

- **Request timings:** In a separate fresh verification run, all 16 IP India source URLs downloaded successfully. Average request duration: 0.923 seconds; median: 0.255 seconds; slowest document request: 4.014 seconds. For FastAPI, the GitHub commit API request took 0.659 seconds and the single ZIP archive download took 8.396 seconds (19.465 MB). The ZIP measurement is archive-level, not 1,696 individual request timings.

- **Retries:** None of the 16 IP India requests in the verification run needed more than one attempt. In the historical manifest, 0 of the 20 IP India records with an attempts field required more than one attempt. FastAPI files were extracted from one repository ZIP archive, so per-file retry counts are unavailable.

## D07 - Parsing the corpus

### Parser implementation
- Added PDF parsing using PyMuPDF and pypdf.
- Added HTML, Markdown, text and structured-data parsing.
- Extracted page numbers, heading paths and Markdown content.
- Added ParseFailure table to track parsing errors.
- Added idempotent parsing to avoid duplicate documents.
- Added Tesseract OCR fallback for scanned PDFs.

### Full corpus results
- Total downloaded files: 1,716
- Initially parsed: 1,687
- Initially failed: 7
- Initially skipped: 22
- Initial pages created: 4,499

### OCR recovery
- Installed Tesseract OCR 5.4.0.
- Successfully recovered 5 scanned PDFs using OCR.
- Additional pages created: 137
- Remaining parse failures: 0

### Idempotency verification
- Second full run: parsed=0, failed=0, skipped=1,716, pages=0.
- Confirmed that existing parsed documents were not duplicated.

### Quality checks
- Unit tests: 70 passed.
- Ruff lint: Passed.
- Ruff format: 54 files already formatted.

### Known limitation
- OCR extraction may not perfectly preserve complex tables, layouts or scanned text.

### Parser comparison
- Added the official EPO Guidelines 2026 PDF to the corpus; total comparison sample is now 10 PDFs.
- Compared PyMuPDF and pypdf on all 10 PDFs.
- PyMuPDF: 5 successful, 5 failed; 1,406 pages; 3,504,144 characters; 141.927 seconds.
- pypdf: 9 successful, 1 failed; 1,491 pages; 3,595,096 characters; 187.443 seconds.
- pypdf succeeded on more files in this sample, while PyMuPDF was faster overall.
- EPO PDF: both parsers extracted 1,092 pages. PyMuPDF took 13.863 seconds; pypdf took 150.438 seconds.
- Disabled table detection only for the EPO PDF during comparison to avoid excessive processing time. Default parser table extraction remains enabled.
- Detailed results are saved in data/parser_comparison.csv.

### Retry and progress features
- Added --retry-failed to process only files currently listed in parse_failures.
- Successful retries remove their previous failure records.
- Failed retries increment the attempts count.
- Added progress summaries every 50 processed files and at the end.
- Verified --retry-failed with zero remaining failures: 0 files processed.
- Ruff lint and formatting passed.
- Tests: 70 passed.

### Final failure verification
- Total documents in database: 1,732.
- Remaining parse failures: 0.
- Missing source URLs: 0.
- 0 failures out of 1,716 downloaded corpus files; 20 Schedule_2 entries share one source PDF and have distinct external IDs and hashes.

<!-- STEP 5 PARSER COMPARISON START -->
### Step 5 - Ten hard files parser comparison

Compared 10 files. Default selection uses the 10 largest unique downloaded PDF/HTML files from the manifest.
PDF parsers: PyMuPDF and pypdf. HTML parsers: Trafilatura and strip-tags. Text/data files use the plain parser.

| File | Parsers (A / B) | Pages | A found | B found | Time (A / B) | Better, why |
|---|---|---:|---|---|---|---|
| 7fdd559b-1ff8-4a87-8c36-033e7356b39b-9c1fa2de.pdf | pymupdf / pypdf | 67 / 67 | 148,067 chars; 191 headings; 13 tables | 146,715 chars; 0 headings; 0 tables | 11.348s / 5.46s | PyMuPDF: both extract the contents, but PyMuPDF preserves heading structure (191 vs 0). |
| e1adfe40-7af3-4180-ba04-2e0099c6dca5-825601cc.pdf | pymupdf / pypdf | 174 / 174 | 351,343 chars; 493 headings; 180 tables | 318,569 chars; 0 headings; 0 tables | 41.812s / 11.813s | PyMuPDF: both extract readable text; PyMuPDF preserves headings (493 vs 0), despite being slower. |
| 2748c8f6-ca59-4bb9-b5e9-690a7a934136-e149111f.pdf | pymupdf / pypdf | 0 / 0 | FAILED: no_text_layer: 0 characters on 52 pages | FAILED: no_text_layer: almost no text on 52 pages | 5.457s / 0.09s | Neither: Both comparison parsers failed; separate Tesseract OCR test successfully recovered 52 pages and 87,422 characters (150 DPI, full-page OCR; latest verification). |
| 73b5bf10-b04e-4f45-abef-87ff117315dc-dccb9293.pdf | pymupdf / pypdf | 69 / 69 | 242,921 chars; 177 headings; 0 tables | 241,650 chars; 0 headings; 0 tables | 15.976s / 7.673s | PyMuPDF: both extract readable Act text; PyMuPDF preserves headings (177 vs 0). |
| 8a163997-d0d1-45ed-a657-725b31c44f3f-d3b56477.pdf | pymupdf / pypdf | 0 / 73 | FAILED: no_text_layer: 0 characters on 73 pages | 127,818 chars; 0 headings; 0 tables | 20.889s / 3.227s | pypdf: pypdf succeeded; pymupdf failed. |
| 86c74a8b-b029-4b79-812a-d260b2f90368-3f1f5ca8.pdf | pymupdf / pypdf | 4 / 4 | 39,452 chars; 0 headings; 35 tables | 8,068 chars; 0 headings; 0 tables | 1.92s / 0.757s | pymupdf: Extracted 35 tables and 39,452 characters, compared with pypdf's 0 tables and 8,068 characters; verify table layout against the source. |
| d7bed07b-5c56-404b-a0c8-152b4bd18f0f-c9215741.pdf | pymupdf / pypdf | 0 / 8 | FAILED: no_text_layer: 95 characters on 8 pages | 12,788 chars; 0 headings; 0 tables | 7.088s / 1.36s | pypdf: pypdf succeeded; pymupdf failed. |
| forms-and-official-fees-78ff0e5f.html | trafilatura / strip-tags | 1 / 1 | 948 chars; 0 headings; 3 tables | 18,437 chars; 8 headings; 1 tables | 0.448s / 0.043s | trafilatura: Manual inspection confirmed the fees table in Markdown; strip-tags retained extensive unrelated navigation. |
| basics-of-patents-593130e6.html | trafilatura / strip-tags | 1 / 1 | 2,079 chars; 0 headings; 0 tables | 19,546 chars; 9 headings; 0 tables | 0.245s / 0.04s | trafilatura: Manual inspection confirmed useful patent sections and bullet content; strip-tags retained navigation noise. |
| faqs-d3efbe1e.html | trafilatura / strip-tags | 1 / 1 | 211 chars; 0 headings; 0 tables | 17,474 chars; 7 headings; 0 tables | 0.473s / 0.061s | Neither: Trafilatura extracted only a PDF-unavailable message; strip-tags mainly retained navigation, not FAQ answers. |

**Inspection note:** Compare extracted pages with original sources. Check tables, headings, repeated headers/footers and unwanted characters; higher character counts alone do not mean better extraction.

**PDF note:** PyMuPDF table extraction was disabled only for the EPO Guidelines comparison to avoid excessive processing time.

Detailed per-parser results: `data/parser_comparison.csv`.
<!-- STEP 5 PARSER COMPARISON END -->

### SQL inspection - three parsed documents

Inspected parsed pages from three documents in Neon PostgreSQL.

| Document ID | Document title | Inspection result | Issues found |
|---|---|---|---|
| 1718 | Patent Cooperation Treaty | Pages 1-5 contain readable Patents Act, 1970 table-of-contents text. | Title does not match extracted content; headings array is empty on all five pages. Verify source-to-document metadata mapping. |
| 1729 | CRI Guidelines Annexure I | Pages 1-5 contain readable technical examples and explanations. | Headings array is empty on all five pages despite visible section labels. Check formula formatting on page 5 against the original PDF. |
| 1717 | The Patents Rules, 2003 | Page 1 contains the title, table of contents heading and disclaimer text. | Headings array is empty even though Markdown heading markers are present in the extracted text. Only one page was returned in this query. |

**Observed parsing issues and possible fixes:**
- Heading extraction: investigate why headings are not being populated even when headings are visible in extracted text. Improve heading detection for PDF and HTML documents.
- Metadata mapping: verify why document ID 1718 is titled Patent Cooperation Treaty while its extracted text begins with The Patents Act, 1970.
- Formula preservation: compare mathematical expressions in the CRI document with the original PDF to check whether symbols and formatting are preserved.
- HTML structure: verify that Markdown-style heading markers are also represented in the structured headings field.

**Inspection limitation:** These observations are based on the SQL output returned for the selected pages. They do not establish that every page of these documents has the same issues.

### Plain-text parser heading verification

Tested the Markdown parser using `data/raw/fastapi-fastapi/docs/de/llm-prompt.md`.

- Parsing completed successfully and returned 4 pages.
- Heading extraction detected `Target language`, `Grammar to use when talking to the reader`, `Headings`, and other section headings.
- Text content was readable and Markdown heading markers were preserved in the extracted text.
- Some headings repeat across pages because the document is split into multiple pages.
- Result: plain-text parser heading extraction works on this Markdown sample.

## Day 8 - Final LLM latency verification

### Initial Gemini measurement

- Provider: Gemini
- Model: gemini-3.6-flash
- First-word latency: 21.726 seconds
- Target: less than 1.5 seconds
- Result: NOT PASS
- Total response time: 27.032 seconds

### Optimized Groq measurement

- Primary provider: Groq
- Model: openai/gpt-oss-20b
- Fallback provider: Gemini
- First-word latency across 5 consecutive tests: 0.693-0.915 seconds
- Average first-word latency: approximately 0.802 seconds
- First-word target: less than 1.5 seconds
- Result: PASS in all 5 measured runs
- Additional streaming verification: 0.706 seconds first-word latency
- Streaming total response time: 1.136 seconds
- Non-streaming JSON latency: 1.405 seconds
- JSON output: successful
- Fallback used in verification: No
- Request ID log matching: PASS
- Unit tests: 99 passed
- Ruff lint and format checks: PASS
- Local CLI uses 127.0.0.1 to avoid Windows localhost resolution delay
- Patent documents are not connected to the LLM yet; responses use general model knowledge

### Step 5.1 - English vs Tamil tokens
- Hi baseline: 219 tokens
- English refund question: 227 tokens; message tokens = 8
- Tamil refund question: 241 tokens; message tokens = 22
- Tamil/English ratio: 2.75x

### Step 5.2 - Questions the model cannot know
- Patent grant question: PASS. The model said it was not sure and explained that grant depends on novelty, inventive step, industrial applicability, and compliance with the Indian Patents Act. It did not guarantee grant.
- Off-topic cricket question: PASS. The model declined in one sentence: 'This question is unrelated to patents.'
- Known-answer test 1 (Section 3(k)): MISS. The response text was empty; usage reported tokens_out=2048. Correctness could not be verified.
- Known-answer test 2 (Form 1): Mostly correct. It correctly described Form 1 as the Indian patent application form and listed applicant/invention/inventor/signature/fee details. Caveat: saying submission automatically triggers the official filing date is simplified; filing date depends on applicable filing requirements.
### Step 5.3 - Fallback and circuit breaker
- Invalid Gemini model: PASS. First three calls tried Gemini, failed with 404, and fell back to Groq.
- Fourth call: PASS. Circuit was open; Gemini was skipped and Groq answered.
- Half-open retry after 30 seconds: PASS. Gemini was tried again, failed, and Groq answered.
- Restored model: Gemini request returned an error during the verification call; normal Gemini success is not yet confirmed.
- Restored Gemini model verification: PASS. Gemini answered successfully with fallback=False, 159 input tokens, 120 output tokens, and estimated cost ₹0.033031.
- Restored Gemini model verification: PASS. Gemini answered successfully with fallback=False, 159 input tokens, 120 output tokens, and estimated cost ₹0.033031.
### Step 5.4 - Usage and database verification
- Neon SQL verification: PASS. Successful Gemini call, failed Gemini attempts, Groq fallback records, token counts, latency, estimated cost, and fallback flags are stored in llm_calls.
- Recovery verified: restored Gemini model completed successfully with fallback=False.

### Step 6 - Render deployment and live LLM verification

#### Docker and deployment
- Docker prompt fix: PASS.
- Added `COPY --chown=app:app prompts ./prompts` to the Dockerfile.
- Local Docker image build: PASS.
- Render deployment health: PASS.
- Live health endpoint: `/health`.
- Health status: `ok`.
- Deployed Git SHA: `f5ff95b100251928f6ed18787dd57a77e73fc022`.

#### First live chat request
- Endpoint: `https://patentpath.onrender.com`
- Question: What is a provisional patent specification?
- Result: PASS. A response was returned.
- Provider: Groq (fallback).
- Model: `openai/gpt-oss-20b`.
- Input tokens: 225.
- Output tokens: 802.
- Estimated request cost: INR 0.02446.
- Attempts: 1.
- Fallback used: Yes.
- First-word latency: 3.951 seconds.
- Total response time: 5.112 seconds.

#### Live usage endpoint
- Endpoint: `/v1/usage`.
- Date: 2026-11-25.
- Total API calls: 72.
- Errors: 18.
- Fallbacks: 16.
- Input tokens: 14,367.
- Output tokens: 18,358.
- Estimated total cost: INR 0.6574.

#### Second live chat request
- Result: PASS. A response was returned.
- Provider: Groq (fallback).
- Model: openai/gpt-oss-20b.
- Input tokens: 225.
- Output tokens: 300.
- Estimated request cost: INR 0.010153.
- Attempts: 1.
- Fallback used: Yes.
- First-word latency: 4.037 seconds.
- Total response time: 5.261 seconds.

#### Deployment issue and fix
- Initial Render deployment failed because `prompts/chat_system_v1.md` was missing from the Docker runtime image.
- Fixed by copying the prompts directory into the Docker image.
- Local Docker build and subsequent Render health check passed.

### Latency baseline

Measured from the Neon `llm_calls` table:

- p50 latency: 875 ms (0.875 seconds)
- p95 latency: 21,724.6 ms (21.72 seconds)
- Day 1 target: p95 under 6 seconds
- Status: Target not met; investigate slow calls and fallback latency.

## Stretch 2 - Circuit breaker status API

- Added GET /v1/llm/status to report provider name, model, and breaker state.
- Added two FakeLLM tests for closed and open breaker states.
- Live experiment: invalid Gemini model caused primary failures; Groq fallback succeeded; the Gemini breaker reached half-open after the cooldown.
- Restored the original Gemini model after the experiment.

Day 9 Step 2: Classmate reviewed all 20 question labels. No unclear labels remained.

Day 9 Step 2: Classmate reviewed all 20 question labels and agreed. No label changes needed.
