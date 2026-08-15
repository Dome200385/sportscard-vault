# SportsCard Vault V0.15.13 – Persistent Postgres Image Fallback

Supabase Storage/S3 currently returns HTTP 400 (including `Project not specified`) from the Render environment even though the direct Storage hostname resolves, the bucket exists, and S3 credentials are configured.

V0.15.13 keeps S3 as the preferred image backend, but if S3/Storage fails it persists the already-scanned image bytes in the working Supabase Postgres connection (`card_image_blobs`). Card instance paths use `pgimg://<uuid>` and the API serves those images through `/api/v1/images/<uuid>`.

This removes Render `/tmp` image loss and allows production persistence while the Supabase Storage routing issue remains isolated. No new Render environment variables are required.
