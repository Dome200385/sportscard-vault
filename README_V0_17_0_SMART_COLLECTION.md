# SportsCard Vault V0.17.0 – Smart Collection

Built on the deployed V0.16.0 mobile web UI patch.

## New
- Collection search plus filters for Rookie, Autograph, Relic and serial-numbered cards.
- Sorting by recent, player name and release year.
- Visual RC/AUTO/RELIC/numbered badges on card tiles.
- Duplicate-instance indicator when a card identity has multiple owned instances.
- Valuation panel in card detail using the existing `/api/v1/cards/{card_id}/valuation` endpoint.
- Scan review highlights lower-confidence fields and surfaces duplicate warnings.
- Version bumped to V0.17.0.

## Unchanged / protected
- Existing scan/analyze flow.
- `confirm-scan-auto` save flow.
- Postgres database persistence.
- Postgres image fallback and image readback.
- Existing Render/Supabase environment configuration.

No new environment variables or database migration are required.
