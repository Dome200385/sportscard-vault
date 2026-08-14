# SportsCard Vault V0.15.4 – Native Postgres Persistence

## Ziel
Die bereits erfolgreich getestete Supabase/Supavisor Session-Pooler-Verbindung wird jetzt als aktive, dauerhafte Datenbank für Kartendaten verwendet. Die fehlerhafte Supabase-REST-DNS-Auflösung blockiert die Kartendaten nicht mehr.

## Änderungen
- Neuer Provider `backend/app/postgres_db.py` über `SUPABASE_DATABASE_URL`.
- `DATABASE_PROVIDER=supabase` bevorzugt jetzt nativ Postgres; SQLite ist nur Notfall-Fallback.
- Idempotente Start-Migration erweitert das vorhandene Legacy-Schema um JSON-Felder, Identity-Fingerprint, Scanstatus und `scan_corrections`.
- Collection, Card Detail, Scan History, Corrections, Comps und CSV-Export funktionieren über Postgres.
- API/UI-Version auf 0.15.4 angehoben.
- `persistence-check` wertet den aktiven Provider `postgres` als persistent.

## Bewusst noch offen
Supabase Storage läuft weiterhin über die Project REST URL. Solange Render deren DNS nicht auflösen kann, bleiben Kartenbilder im lokalen Fallback und `ready_for_mass_collection=false`. Die Kartendaten selbst können ab V0.15.4 trotzdem dauerhaft in Postgres gespeichert werden.

## Tests
- Python compileall: erfolgreich
- Bestehende Backend-Tests: 13/13 bestanden (`PYTHONPATH=. pytest -q`)
