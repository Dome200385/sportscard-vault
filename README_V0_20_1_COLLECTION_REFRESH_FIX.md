# SportsCard Vault V0.20.1 — Collection Market Refresh Fix

This hotfix keeps the working V0.20.0 SoldComps single-card pipeline and fixes the collection-wide refresh that could surface as `Failed to fetch` in the web UI.

## What changed
- Unique SoldComps fingerprint queries are now executed concurrently instead of sequentially.
- Duplicate queries still consume only one SoldComps API request per collection refresh.
- Database ingestion remains sequential and deterministic after provider responses return.
- Collection refresh response exposes `unique_queries` and `parallel_workers` diagnostics.
- The web UI now reports HTTP errors explicitly and reloads already persisted market data even if the bulk refresh request fails.
- Version bumped to 0.20.1.

## No configuration changes
No new Render environment variables or Supabase changes are required.

## Validation
- Python compile check passed.
- Frontend JavaScript syntax check passed.
- Market provider tests: 3 passed.
