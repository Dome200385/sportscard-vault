# SportsCard Vault V0.14 – Persistent Collection

## Implemented
- Dual persistence layer: SQLite test mode + Supabase production mode.
- Supabase/Postgres implementation for card identities, owned instances, scans, corrections, comps and export.
- Persistent image upload to private Supabase Storage bucket `card-images`.
- Scan images are uploaded only after Vision has finished; Render `/tmp` is no longer the source of truth when Supabase is active.
- One exact card identity can still own multiple physical instances.
- Signed image URLs are generated server-side when reading card details.
- Preflight now reports database persistence, image persistence, Supabase configuration and `ready_for_mass_collection`.
- Existing SQLite mode remains intact until Supabase is configured, so deploying V0.14 cannot destroy the working scanner.

## Activation checklist
1. Create Supabase project.
2. Run `supabase/schema_v0_14.sql` in SQL Editor.
3. Create private Storage bucket `card-images`.
4. Add `SUPABASE_URL` and `SUPABASE_SECRET_KEY` only in Render environment variables.
5. Set `DATABASE_PROVIDER=supabase` in Render.
6. Redeploy and verify `/api/v1/system/preflight` shows:
   - database_provider: supabase
   - database_persistent: true
   - image_storage_persistent: true
   - ready_for_mass_collection: true
7. Scan + save one test card, redeploy/restart Render, verify the card still exists.

Do not expose `SUPABASE_SECRET_KEY` in GitHub or browser code.
