# SportsCard Vault V0.15.14 — Postgres image read-back fix

This patch hardens the Postgres image fallback after a real scan produced a `pgimg://...` reference but `/api/v1/images/{image_id}` returned 404.

Changes:
- `persist_image_blob()` now commits and verifies the image through a fresh Postgres connection before returning an id.
- `get_image_blob()` accepts either a bare UUID or `pgimg://UUID` and queries with `id::text` for pooler-safe lookup.
- `/api/v1/images/{image_id}` also accepts either form.
- `image_blob_ready()` is now an actual write → re-read → delete probe, so `image_storage_persistent:true` cannot be reported just because the table exists.

No Render environment-variable changes are required.
