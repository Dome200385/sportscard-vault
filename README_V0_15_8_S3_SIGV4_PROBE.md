# SportsCard Vault V0.15.8 – Raw SigV4 S3 Probe

V0.15.8 targets the remaining Supabase S3 HTTP 400 response after endpoint, region and server-side credentials were confirmed.

## Changes
- Builds S3 URLs explicitly so the `/storage/v1/s3` prefix is preserved exactly.
- Signs requests with botocore `S3SigV4Auth` and sends them with `httpx`.
- Exposes the raw HTTP status/body from Supabase for precise diagnostics.
- Adds a tiny `_health/` write → HEAD → delete probe to validate the exact operations needed for card images.
- Uses the same explicit signed PUT flow for real card-image persistence.
- Presigned private image URLs use `S3SigV4QueryAuth`.

The health object is deleted immediately after the probe. No collection data is modified.
