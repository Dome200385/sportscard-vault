# V0.14 Supabase setup

The code is deliberately deployed in SQLite mode first. Activate Supabase only after the project, schema and bucket exist.

### Supabase
- Create a project named `SportsCard Vault`.
- SQL Editor: run `supabase/schema_v0_14.sql`.
- Storage: create a **private** bucket named `card-images`.
- Project Settings / API: copy Project URL and the server-side **secret** key. Never use the secret key in browser code.

### Render environment
Add:
- `SUPABASE_URL` = project URL
- `SUPABASE_SECRET_KEY` = server secret key
- `SUPABASE_BUCKET` = `card-images`

Change:
- `DATABASE_PROVIDER` from `sqlite` to `supabase`

Keep:
- `OPENAI_API_KEY` unchanged.

Redeploy. Then open `/api/v1/system/preflight` and only proceed to mass collection after `ready_for_mass_collection` is true.
