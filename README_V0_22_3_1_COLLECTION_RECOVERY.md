# SportsCard Vault V0.22.3.1 — Collection Recovery

This hotfix makes the collection UI resilient when one of the market/performance endpoints fails.

- Core collection and card images load independently from market-history endpoints.
- Performance-baseline creation is non-blocking.
- A market API failure can no longer blank the whole collection screen.
- Existing persistent collection data is never deleted or reset by this patch.
- No environment variable or database migration changes.

Deploy with the existing folder structure so the files replace:
- backend/static/index.html
- backend/app/main.py
