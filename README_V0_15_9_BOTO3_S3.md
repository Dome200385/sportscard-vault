# SportsCard Vault V0.15.9 – Official boto3 S3 path

V0.15.9 removes the hand-built SigV4 HTTP path from V0.15.8 and returns to the official AWS SDK request construction recommended for Supabase S3-compatible Storage.

## Why

The V0.15.8 raw request reached the Storage gateway but returned `Project not specified`. V0.15.9 therefore lets botocore construct and sign the complete request using:

- the exact Supabase S3 endpoint from Render,
- the exact project region,
- the generated S3 access-key pair,
- Signature V4,
- path-style bucket addressing.

The readiness probe performs `ListObjectsV2` plus a tiny `PutObject -> HeadObject -> DeleteObject` roundtrip in `_health/`.
