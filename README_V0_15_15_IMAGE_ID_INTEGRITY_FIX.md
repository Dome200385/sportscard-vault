# SportsCard Vault V0.15.15 — Image ID integrity fix

- Disables SHA-based reuse of old Postgres image IDs.
- Every newly uploaded scan image gets a fresh application-generated UUID.
- INSERT is committed and verified through a fresh DB connection before `pgimg://` is returned.
- Reads use a UUID-typed SQL predicate.
- Adds `GET /api/v1/images/{image_id}/meta` for safe existence diagnostics.
- Image responses include `X-Image-Storage: postgres`.

## Test after deploy
1. `/health` must report `0.15.15`.
2. Run a completely new `/api/v1/scan/analyze`.
3. Read that scan and copy the NEW `front_image_path` UUID. It must differ from the old `8b0473fc-...` ID.
4. Call `/api/v1/images/{new_id}/meta` -> `exists: true`.
5. Call `/api/v1/images/{new_id}` -> HTTP 200 image bytes.
