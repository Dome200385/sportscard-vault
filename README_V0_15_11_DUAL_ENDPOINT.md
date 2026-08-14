# SportsCard Vault V0.15.11 – Dual Supabase S3 endpoint diagnostic

This release keeps the configured production S3 endpoint unchanged and performs read-only comparison probes against both Supabase S3 endpoint forms:

- direct storage host: `https://<project-ref>.storage.supabase.co/storage/v1/s3`
- project host: `https://<project-ref>.supabase.co/storage/v1/s3`

The persistence check reports DNS, HeadBucket, ListObjectsV2, request URL, safe HTTP/error metadata, and identifies a usable endpoint if one succeeds. No credentials are exposed and the alternate endpoint probe does not write objects.
