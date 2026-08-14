# V0.15.8

- Native Postgres persistence retained.
- Supabase S3 credentials, endpoint and region retained.
- Replaced boto3 routing for storage requests with explicit raw SigV4 requests.
- Added raw S3 response diagnostics and isolated write/head/delete readiness probe.
- Real image uploads now use the same signed request path as the successful probe.
