# SportsCard Vault V0.22.6.5

Defensive valuation peer-evidence fix.

- Fixes identical estimates caused by false==false feature matches.
- Only positive card traits contribute to feature similarity.
- Adds player/product/set/parallel/year/team/print-run/card-number weighting.
- Rejects weak peers instead of using a collection-wide fallback price.
- Removes stale V4 defensive estimates when V5 cannot justify them.
- Verified market values remain authoritative and unchanged.
