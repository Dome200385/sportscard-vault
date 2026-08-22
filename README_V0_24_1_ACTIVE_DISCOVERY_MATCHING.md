# SportsCard Vault V0.24.1 — Active Discovery Matching

- Active listings now use a discovery-first query ladder (player+card number, player+insert, product+player).
- Provider results are deduplicated before local identity scoring.
- Active-only matching has two transparent tiers: `strict` and `probable`.
- `probable` requires exact player identity plus strong product/insert evidence and rejects dangerous mismatches; it never becomes a sold comp.
- UI shows raw hits → unique candidates → usable matches when no active market can be shown.
- Active asking prices remain display-only and never affect portfolio value, performance, verified comps, or AI training.
- Sold-market matching remains unchanged and strict.
