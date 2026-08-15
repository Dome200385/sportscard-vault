# SportsCard Vault V0.15.12 – Storage split diagnostic

V0.15.12 keeps the production Postgres and S3 behavior unchanged and adds an independent, read-only Supabase Storage REST probe.

The goal is to separate two questions:

1. Does the direct Storage service accept the configured server-side Supabase secret and expose `card-images` via the REST Storage API?
2. Does the S3-compatible protocol accept the generated S3 access-key pair and SigV4 requests?

The persistence check now exposes `storage_rest_split_trial`, `storage_rest_split_any_ok`, and `storage_s3_split_any_ok`. No secret values are returned.
