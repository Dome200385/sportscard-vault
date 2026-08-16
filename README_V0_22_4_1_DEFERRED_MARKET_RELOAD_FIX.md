# SportsCard Vault V0.22.4.1 – Deferred Market Reload Fix

- Collection cards stay fast/paginated.
- Persisted current market values are loaded by a lightweight summary endpoint.
- Portfolio history loads independently, so a slow history request cannot hide card prices.
- Normal collection loading never calls SoldComps.
- No DB migration or new environment variables.
