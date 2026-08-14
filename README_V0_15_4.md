# V0.15.4 Patch

Inhalt ins bestehende GitHub-Repository hochladen und gleichnamige Dateien ersetzen.

Es sind keine neuen Render-Variablen nötig. `SUPABASE_DATABASE_URL` muss weiterhin auf den bereits getesteten Session-Pooler zeigen.

Nach dem Deploy:
1. `/api/v1/system/persistence-check` öffnen.
2. Erwartet: `database_active_provider: "postgres"`, `database_persistent: true`, `database_connection: true`.
3. Eine Testkarte scannen und speichern.
4. Render erneut deployen/restarten.
5. Sammlung aktualisieren: Testkarte muss weiterhin vorhanden sein.

`ready_for_mass_collection` bleibt voraussichtlich noch `false`, bis der Bildspeicher persistent ist.
