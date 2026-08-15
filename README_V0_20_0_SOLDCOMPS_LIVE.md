# SportsCard Vault V0.20.0 — SoldComps Live Pricing

V0.20.0 activates the first live sold-market provider. `SOLDCOMPS_API_KEY` stays server-side in Render.

## What is new

- Searches SoldComps `/v1/scrape` for real completed eBay sales.
- Uses one request per unique card fingerprint during a collection refresh, so duplicate cards do not waste quota in the same run.
- Matches seller titles against player, card number, product, parallel, raw/graded state and card traits.
- Rejects obvious lots, breaks, reprints and graded listings when valuing a raw card.
- Uses the all-in sold price when available and excludes robust statistical outliers.
- Stores accepted sales as persistent verified comps, including URL, sold date, match confidence and source item ID.
- Avoids duplicates when the same sold listing is returned on a later refresh.
- Records a price-history snapshot after new comps are persisted.
- Collection and detail views immediately show market value, comps and price history.

## Environment

Required:

`SOLDCOMPS_API_KEY=sc_...`

Optional defaults:

- `SOLDCOMPS_EBAY_SITE=ebay.com`
- `SOLDCOMPS_DAYS=90`
- `SOLDCOMPS_COUNT=120`
- `SOLDCOMPS_TIMEOUT_SECONDS=30`

## Pricing policy

Only completed/sold listings are ingested automatically. Active asking prices are never treated as market value, and no AI-generated price is used.
