# V0.15.10

- Kept official Supabase direct-storage S3 endpoint and path-style addressing.
- Removed forced `payload_signing_enabled=True`; botocore now uses its default behavior.
- Added HeadBucket probe before ListObjectsV2.
- Added safe request URL/path and credential-shape diagnostics without exposing secrets.
