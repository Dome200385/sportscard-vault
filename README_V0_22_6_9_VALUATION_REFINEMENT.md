# SportsCard Vault V0.22.6.9 – Valuation Refinement

V0.22.6.9 keeps the working card-feature hydration and persistence from V0.22.6.8, but refines the defensive model so cards with no strong semantic peer no longer inherit the same portfolio/category anchor by default.

## Changes
- Adds a soft-peer evidence layer using the nearest verified cards with similarity score >= 2.0.
- Soft peers are weighted by similarity and blended with category anchors.
- Feature multipliers are normalized against the selected peer set.
- Strong verified-peer matches still take precedence.
- Category-only fallback remains available only when no usable peer evidence exists.
- Verified SoldComps remain authoritative and are never overwritten.

The goal is fewer artificial price ties while keeping every difference grounded in actual verified collection values rather than arbitrary per-card noise.
