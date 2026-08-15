# SportsCard Vault V0.19.0 – Market Provider Architecture

- Provider-neutral market fingerprint per card.
- Explainable candidate matching with hard checks for player, card number and parallel.
- Separate concepts for verified sold comps vs provider aggregate estimates.
- No automatic provider is enabled yet; no active listing is treated as a sold comp.
- New endpoints: `/api/v1/market/providers`, `/api/v1/cards/{id}/market-fingerprint`, `/api/v1/cards/{id}/market/refresh`, `/api/v1/market/match-preview`.
- UI shows the card fingerprint and an explicit provider status in card details.
