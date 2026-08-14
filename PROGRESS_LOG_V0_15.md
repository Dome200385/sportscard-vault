# SportsCard Vault V0.15

## Ziel
Massensammlungs-Readiness sauber prüfbar machen und Versionsstand eindeutig halten.

## Neu
- API-/Health-Version auf 0.15.0 angehoben.
- `/api/v1/system/persistence-check` prüft Datenbank, Supabase-Konfiguration und Storage-Bucket ohne Karten zu verändern.
- Scanner zeigt V0.15.
- V0.14-Supabase-Persistenz bleibt vollständig enthalten.

## Freigabekriterium für 4.000+ Karten
`ready_for_mass_collection` muss `true` sein. Erst dann Massenerfassung starten.
