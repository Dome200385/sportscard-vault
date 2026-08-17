# V0.22.6.4 – Weighted Card Similarity

- Keeps V0.22.6.3 server-side persistence unchanged.
- Fixes identical defensive estimates caused by median-based peer bands.
- Uses similarity-squared weighting so the closest verified cards dominate each estimate.
- Uses card features (rookie, auto, relic/RPA, numbered, insert/short-print), player, product/set, year and team.
- Verified SoldComps always override defensive estimates.
- Fixes per-card anchor leakage between loop iterations.
