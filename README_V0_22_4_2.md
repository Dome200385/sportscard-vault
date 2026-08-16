# SportsCard Vault V0.22.4.2

Fix for deferred persisted market-data reload.

- Keeps fast first paint / paginated collection feed.
- Reuses the proven per-card persisted market-state calculation for deferred values.
- Uses sequential DB reads in the deferred summary to avoid concurrency/client edge cases.
- Does not call SoldComps while opening the collection.
- Full portfolio history remains a separate deferred request.
- No DB migration or new environment variables.
