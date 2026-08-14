# SportsCard Vault V0.15.6 — S3 Wiring Hardening

V0.15.6 hardens persistent Supabase Storage configuration after V0.15.5 showed that the app still fell back to the legacy REST hostname.

## Changes

- Accepts `SUPABASE_S3_*` variables plus common `S3_*`, `AWS_*`, and `S3FS_*` aliases.
- Automatically derives the Supabase S3 endpoint from `SUPABASE_URL` when an endpoint was omitted.
- If a project base URL was pasted as the S3 endpoint, it is converted to the actual S3 protocol endpoint.
- Prefers the direct Storage hostname: `https://<project-ref>.storage.supabase.co/storage/v1/s3`.
- Derives the AWS region from the Supavisor database host when `SUPABASE_S3_REGION` is missing (for this project: `eu-west-3`).
- Persistence diagnostics now expose only non-secret booleans for S3 credentials and the derived endpoint/region.

No S3 secret is ever returned by the API.
