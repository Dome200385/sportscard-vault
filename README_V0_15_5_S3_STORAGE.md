# SportsCard Vault V0.15.5 – Persistent S3 Image Storage

V0.15.5 keeps the working native Postgres/Supavisor database path from V0.15.4 and moves card-image persistence to Supabase Storage's S3-compatible API.

## Render environment variables

Keep existing variables unchanged and add:

- `SUPABASE_S3_ENDPOINT` – copy from Supabase Storage > S3 Configuration (prefer the direct storage endpoint when Supabase offers it)
- `SUPABASE_S3_REGION` – copy exactly from the same Supabase S3 configuration page
- `SUPABASE_S3_ACCESS_KEY_ID` – generated S3 Access Key ID
- `SUPABASE_S3_SECRET_ACCESS_KEY` – generated S3 Secret Access Key
- `SUPABASE_BUCKET=card-images` (already present)

All S3 credentials are server-side secrets. Never put them in GitHub or the browser frontend.

## Expected persistence check

`GET /api/v1/system/persistence-check` should show:

- `database_active_provider: postgres`
- `database_persistent: true`
- `storage_provider: supabase-s3`
- `storage_dns_ok: true`
- `storage_bucket_exists: true`
- `image_storage_persistent: true`
- `ready_for_mass_collection: true`

## Acceptance test

1. Scan front + back.
2. Save the card.
3. Open the card detail and verify front/back signed image URLs.
4. Restart or redeploy Render.
5. Re-open the same card detail. Card data and both images must still be available.
