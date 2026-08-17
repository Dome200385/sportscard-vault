# SportsCard Vault V0.22.6.7 – Hybrid Feature Model

- Replaces identical fallback pricing with a card-specific hybrid valuation model.
- Uses verified peer matches when available.
- Blends same-player/product/set/team/year anchors from verified collection data.
- Uses a conservative lower-quantile collection anchor only as last resort.
- Positive card traits (rookie, autograph, relic, RPA, insert, SP/SSP, case hit, serial numbering) affect each target individually.
- Feature premiums are learned from verified collection data when enough examples exist; otherwise modest conservative priors are used.
- Verified SoldComps always remain authoritative and are never overwritten.
- Defensive estimates remain separately persisted and excluded from official market-performance history.
