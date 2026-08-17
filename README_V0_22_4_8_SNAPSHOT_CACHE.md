# SportsCard Vault V0.22.4.8 – Snapshot Cache Performance

- Normal collection loads use the newest persisted portfolio snapshot as a precomputed market-summary cache.
- Existing pre-V0.22.4.8 snapshots are used immediately through their stored positions, so no new market refresh is required just to get the speed benefit.
- Explicit collection market refresh computes the full summary once and stores it in the snapshot metadata for future instant reads.
- Portfolio history uses durable collection snapshots directly when available and skips the expensive per-card legacy history rebuild.
- New cards remain visible immediately; cards not present in the latest market snapshot simply show pending market data until the next explicit market refresh.
- No SoldComps/provider calls are added to normal collection opening.
