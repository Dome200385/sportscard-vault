# SportsCard Vault V0.15.7 – Supabase S3 Bucket Access

V0.15.7 hardens the Supabase S3 integration after V0.15.6 reached the direct Storage host but `HeadBucket` returned HTTP 400.

Changes:
- Uses `ListObjectsV2(MaxKeys=1)` as the primary non-destructive bucket/object-access probe.
- Keeps `ListBuckets` as a secondary diagnostic.
- Reports S3 error code/message/HTTP status in `/api/v1/system/persistence-check`.
- Uses single-request `PutObject` for card images instead of managed `upload_file`.
- Configures boto3 checksum calculation/validation only when required by the protocol.
- `ready_for_mass_collection` now requires real object access, not only bucket visibility.

No Render environment variable changes are required from V0.15.6.
