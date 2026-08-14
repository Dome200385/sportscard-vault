# V0.15 – Supabase Persistenz aktivieren

1. Supabase-Projekt `sportscard-vault` erstellen.
2. `supabase/schema_v0_14.sql` einmal im SQL Editor ausführen.
3. Privaten Storage-Bucket `card-images` erstellen.
4. In Render Environment setzen: `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SUPABASE_BUCKET=card-images`, `DATABASE_PROVIDER=supabase`.
5. Deploy/Restart.
6. `/api/v1/system/persistence-check` öffnen. Erwartet: `ready_for_mass_collection: true`.
7. Eine Testkarte scannen + speichern.
8. Render erneut deployen/restarten. Karte muss weiterhin in Collection vorhanden sein.

Secrets niemals in GitHub oder im Browser-Code speichern.
