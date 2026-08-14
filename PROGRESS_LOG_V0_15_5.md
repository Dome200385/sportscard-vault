# V0.15.5 Progress

- V0.15.4 Postgres persistence retained.
- Added Supabase S3-compatible image storage via boto3.
- Added S3 DNS/bucket diagnostics.
- Added presigned private image URLs.
- Legacy `sb://` references can be signed through S3 when S3 is configured.
- Local filesystem remains a safe fallback until S3 readiness is green.
