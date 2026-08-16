# SportsCard Vault V0.22.4 – Fast Collection

Performance release for growing collections.

## Changes
- Removes browser-side N+1 card-detail requests when opening the collection.
- Adds `/api/v1/collection/feed` with compact paginated card tiles.
- First 12 cards render before market summary/history finishes.
- Additional cards load in 12-card pages via **Weitere Karten laden**.
- Market summary and portfolio history load asynchronously after the first paint.
- Collection thumbnail images request a 480px JPEG variant instead of full originals.
- Existing full-resolution images remain unchanged for card detail.
- Market-summary and market-history card queries use bounded parallel workers.
- SoldComps is never called by ordinary collection loading.
- Existing scan, market refresh, history and manual deletion behavior is preserved.

## Deployment
Upload this patch with its folder structure and replace the existing files:
- `backend/app/main.py`
- `backend/static/index.html`

No new Render environment variables or database migrations are required.

## Validation
- Python compile: OK
- JavaScript syntax check: OK
- Backend test suite: 16/16 passed using SQLite test provider
