# V0.15.7

- Postgres persistence remains unchanged and active.
- Supabase S3 direct endpoint + credentials remain unchanged.
- Replaced HeadBucket-only readiness with ListObjectsV2 object-access probe.
- Added ListBuckets fallback diagnostics and safe S3 error fields.
- Switched scan-image persistence to PutObject.
- Existing test suite must remain green before deploy.
