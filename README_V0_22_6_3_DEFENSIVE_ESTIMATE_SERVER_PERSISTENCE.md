# SportsCard Vault V0.22.6.3

- Defensive AI estimates are now persisted server-side in durable portfolio snapshot metadata.
- Normal market history excludes estimate-storage rows, so AI estimates never fake portfolio performance.
- Existing defensive estimates survive reloads and later estimate runs.
- Verified SoldComps always override/remove AI estimates.
- If no semantic same-player/product/set peer exists, the model uses a conservative card-specific feature proxy anchored to the lower half of verified collection values.
- The previous one-price-for-all fallback is not used.
- No provider/SoldComps request is made by the defensive estimate endpoint.
