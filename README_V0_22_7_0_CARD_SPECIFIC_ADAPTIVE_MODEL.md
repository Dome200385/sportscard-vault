# SportsCard Vault V0.22.7.0 – Card-Specific Adaptive Valuation

V0.22.7.0 fixes the repeated-price saturation seen in V0.22.6.9.

## Root cause
The soft-peer path used one collection-wide hard ceiling. Different cards with different raw model outputs could all hit that same ceiling and therefore display exactly the same price.

## Changes
- Replaces the shared hard ceiling with card-specific adaptive compression.
- The evidence envelope uses the card's own category anchor, feature multiplier and peer base.
- Extreme estimates are compressed, not clipped, so genuine card differences remain visible.
- Adds diagnostics: `raw_estimate`, `adaptive_limit`, and `compressed`.
- Verified SoldComps remain authoritative. Defensive estimates stay separate from market-performance history.
- Existing persistence and image-loading paths are unchanged.
