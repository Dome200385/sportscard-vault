# SportsCard Vault V0.22.4.10 — Instant Market Cache

- Normal collection opening uses `/api/v1/collection/market-cache` only.
- The endpoint reads a single persisted portfolio snapshot and never walks cards/comps.
- No SoldComps/provider calls occur when opening the collection.
- Cards and images remain independent and fast.
- Full market computation remains tied to the explicit “Marktdaten aktualisieren” action.
- Version badge is V0.22.4.10 so deployment can be verified immediately.
