# SportsCard Vault V0.15.10 – S3 request diagnostics

This patch keeps the official boto3 + SigV4 + path-style Supabase S3 client, but removes forced payload signing and adds safe diagnostics for the exact request URL, endpoint path, credential lengths/whitespace, and HeadBucket. No credential values are exposed.

After deployment open `/api/v1/system/persistence-check`.
