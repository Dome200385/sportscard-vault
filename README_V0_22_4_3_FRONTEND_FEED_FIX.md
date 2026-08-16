# SportsCard Vault V0.22.4.3 – Frontend Feed Fix

- Uses the production-proven `/api/v1/collection/feed` URL without query parameters for the first page (defaults: page 1, 12 cards).
- Loads feed and summary sequentially to avoid the false-empty state seen in V0.22.4.2.
- Falls back to the legacy collection route if the fast feed transport fails.
- Never displays “0 cards” merely because a request failed when the collection summary says cards exist.
- Persisted market values and portfolio history remain deferred and do not trigger SoldComps searches.
- Cards stay visible even if the deferred market-summary request fails.
