# SportsCard Vault V0.22.9.0 – SoldComps Debug & Recovery

- Reorders coverage discovery so player + printed card number is the first request.
- ASCII-folds provider search text (e.g. Dončić -> Doncic) without weakening local identity verification.
- Adds player-only and insert-aware fallback discovery strategies.
- Captures SoldComps/eBay diagnostics per attempt: query, totalItems, totalResults, scrapedCount, hasNextPage, auto-selected category, site and soldAfter.
- Collection cards show the latest query used so a zero-result provider response can be diagnosed directly.
- Verified-comp matching rules are unchanged; broader discovery cannot create a market price by itself.
