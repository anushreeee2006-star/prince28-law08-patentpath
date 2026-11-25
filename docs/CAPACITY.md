# Capacity plan: PatentPath

Full corpus target: + CRI guidelines, fee schedules and 200 sample specifications (5,000+ pages).

<!-- generated:start -->
## Measured corpus

- Files: 16
- Measured pages / page equivalents: 946
- PDF pages: 451
- Estimated tokens per page: 396

## Full corpus estimate

- Target: 5,000 pages
- Estimated files: 85
- Estimated tokens: 1.98 million
- Estimated chunks: 3,960 at 500 tokens each
- Embedding cost: $0.40 (about Rs 37.62)
- Vector storage: 15.47 MiB (1024 dimensions, float32)
- Approximate raw text storage: 39.55 MiB (scaled from current corpus)

## Estimation assumptions

- Tokens are estimated from extracted words (1.3 tokens per word), not a tokenizer.
- Chunk count assumes non-overlapping chunks.
- Vector storage excludes PostgreSQL indexes and metadata.
- Embedding price and USD/INR rate are configurable estimates.
<!-- generated:end -->

## What I conclude

1. **Is embedding cost a problem?**

   The estimated embedding cost for the 5,000-page target is about $0.40 (approximately Rs 37.62). This is a relatively small estimated initial cost. Actual cost depends on the embedding model, token count and provider pricing.

2. **Do vectors and text fit in my free Postgres?**

   The estimated vector storage is 15.47 MiB and approximate raw text storage is 39.55 MiB. These estimates are small, but PostgreSQL indexes, metadata and database overhead also require space. My current setup uses local Docker PostgreSQL. I must compare the total actual database size with the storage limit of any hosted free plan before deployment.

3. **Which number am I least sure about, and how will I measure it better?**

   The estimated token count is the least certain because it uses extracted word count multiplied by 1.3 instead of a real tokenizer. I can improve this by using the tokenizer for the selected embedding model and measuring actual tokens from representative documents.

4. **What changes if the corpus grows 10 times?**

   Assuming the same document distribution and chunking strategy, the estimates grow approximately linearly:
   - Tokens: 19.8 million
   - Chunks: 39,600
   - Embedding cost: $4.00 (approximately Rs 376.20)
   - Vector storage: 154.7 MiB
   - Raw text storage: 395.5 MiB

   Retrieval may become slower as the corpus grows. I may need PostgreSQL vector indexes, metadata filters and query optimization.

## Important scope clarification

- The current IP India collection contains 451 PDF pages across 9 PDFs, plus 7 HTML files.
- The measured 946 page equivalents are calculated from the 16 IP India files only; FastAPI and EPO files are excluded.
- The 5,000-page capacity figures are projections for the intended full corpus, not measurements of documents already collected.
- The 200 sample patent specifications are still a collection gap.
