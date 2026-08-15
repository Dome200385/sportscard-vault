# V0.15.13
- Added durable `public.card_image_blobs` table migration.
- S3 remains first choice; Postgres image blobs are automatic fallback.
- Added `/api/v1/images/{image_id}` serving endpoint.
- Persistence diagnostics expose Postgres image fallback readiness.
- `ready_for_mass_collection` can become true when DB data + image bytes are both persistent even if Supabase Storage S3 routing is unavailable.
