# SportsCard Vault V0.22.4.13 – Provider Snapshot Persistence Hotfix

V0.22.4.13 fixes the confirmed cache persistence error from V0.22.4.12.

The central `app.db` facade already forwarded `add_collection_market_snapshot`, but the deployed persistence provider did not expose the matching implementation. This patch ships the provider implementations for PostgreSQL, SQLite fallback and Supabase REST together, including creation/read/write support for `collection_market_snapshots` and `market_price_snapshots`.

Expected result after deploy:
1. Cards and images still load quickly.
2. Run **Marktcache initialisieren** once.
3. The cache persists successfully instead of HTTP 500 / AttributeError.
4. Reload the collection: persisted market data should load from the saved snapshot without a collection-wide comp scan.

No provider/SoldComps request is triggered merely by opening the collection or by cache initialization; rebuild uses already persisted comps only.
