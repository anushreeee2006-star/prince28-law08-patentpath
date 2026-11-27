# PatentPath ingestion report

<!-- generated:start -->
_Generated 27 Nov 2026 22:05 from the database._

| What | Count |
|---|---|
| Documents in the database | 1835 |
| Pages | 7655 |
| Tokens of text (characters Ã· 4) | 11,413,883 |
| Files the parser gave up on | 0 |
| Documents with an extracted record | 215 |
| Documents whose extraction failed | 0 |

| Queue | Count |
|---|---|
| Ingest jobs started | 11 |
| Items finished (done or skipped) | 162 |
| Items that needed more than one try | 41 |
| Items in the dead-letter list | 11 |

Model calls for extraction: 236 Â· tokens in 585,393 Â· tokens out 25,688 Â· cost at list price Rs 22.78

Last job `74fbf9dc5d1344688c2c888ad04d457d`: 20 requested, 20 ok, 0 failed, 5.7 minutes.

Dead-letter list by stage: gave up after 3 attempts 11
<!-- generated:end -->

## What I learnt

1. **Worker stopped during ingestion:** Some items can remain queued or running. Restarting the worker allows unfinished work to be processed again.

2. **Database recovery:** PostgreSQL stores job and item statuses, so the worker can recover unfinished items instead of losing the job state.

3. **Retry proof:** In the worker-kill test, the job completed with 20 done, 0 failed and 425 pages. Seven items needed a second attempt. Across the database, 41 items needed more than one try.

4. **Failures and next investigation:** 11 items reached the dead-letter list after 3 attempts. I would inspect their error details and source records, identify permanent versus temporary failures, then retry suitable items.
