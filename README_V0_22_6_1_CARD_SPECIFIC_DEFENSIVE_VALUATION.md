# SportsCard Vault V0.22.6.1

Card-specific defensive valuation hotfix.

- Removes the collection-wide median fallback that caused identical 5.19 USD estimates.
- Requires a same-player, same-product, or same-set anchor.
- Uses similarity-ranked verified cards, card features, and print-run scarcity.
- Applies a conservative haircut and confidence-dependent range.
- Leaves cards unestimated when no defensible anchor exists.
- Never persists model estimates as verified market values or performance history.
