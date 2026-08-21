# SportsCard Vault V0.23.0 – SoldComps Provider Resilience

- Retries transient SoldComps network/HTTP 500/502/503/504 failures with short exponential backoff.
- Stops a collection coverage run after provider-unavailable/rate-limit/quota errors instead of burning the remaining request budget.
- Tracks runtime SoldComps health in `/api/v1/market/providers`.
- Coverage diagnostics distinguish a provider outage from a genuine zero-result search.
- Existing verified comps and market values remain untouched during provider failures.
- No active-listing prices and no invented AI prices are promoted to verified market value.
