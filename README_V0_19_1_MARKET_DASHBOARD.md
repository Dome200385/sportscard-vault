# SportsCard Vault V0.19.1 – Collection Market Dashboard + Price History

V0.19.1 moves market information into the collection view and adds persistent market-price snapshots.

## New
- Current market value shown directly on every collection card when available.
- 7-day and 30-day percentage change indicators.
- Collection-level total value plus 7-day / 30-day development.
- Last market update timestamp and coverage information.
- Sort collection by market value.
- Per-card price history endpoint and a compact sparkline in card details.
- `Marktdaten ↻` action directly in the collection.
- Persistent `market_price_snapshots` table. Manual verified comps automatically create a snapshot.
- Provider estimates and verified sold comps remain distinct; no AI-invented prices.

## API additions
- `GET /api/v1/cards/{card_id}/market-history`
- `POST /api/v1/collection/market/refresh`
- `GET /api/v1/collection/market-summary` now includes per-card market status and collection trend fields.

## Deployment
No new Render environment variables are required. The active native Postgres provider creates the new snapshot table automatically during startup migration.
