# V0.15.9

- Replaced the manual SigV4/httpx S3 request path with boto3/botocore request construction.
- Uses path-style S3 addressing and SigV4 exactly as documented by Supabase.
- Keeps the live write/head/delete health probe.
- Adds safe boto3 response diagnostics to `persistence-check`.
