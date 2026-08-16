# SportsCard Vault V0.21.0 — Long-term history + delete

- Market snapshots are retained for long-term price history (up to 10,000 points per card).
- A same-value snapshot is retained on a new calendar day, while repeated refreshes on the same day are deduplicated.
- Card detail now shows price-history ranges: 30 days, 90 days, 1 year, all.
- New collection history API: `GET /api/v1/collection/market-history`.
- Owned physical card instances can be deleted from the detail view.
- Deleting one duplicate removes only that instance. If it is the final instance, the identity and its cascaded market data are removed.
- SoldComps remains the source of automatic market comps; no AI-invented prices are introduced.
