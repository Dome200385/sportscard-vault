# SportsCard Vault V0.22.4.9 – Instant Snapshot Cache

Ziel: Normales Öffnen der Sammlung darf niemals mehr alle Karten/Comps neu berechnen.

## Änderungen
- `GET /api/v1/collection/market-summary` ist jetzt cache-only.
- Bestehende Portfolio-Snapshots werden unabhängig von DB-Sortierreihenfolge newest-first durchsucht.
- Vollständige `market_summary_cache` Snapshots werden bevorzugt.
- Ältere Snapshots mit `positions` dienen sofort als kompatibler Fast-Cache.
- Falls noch überhaupt kein kompatibler Snapshot existiert, wird einmalig im Hintergrund ein Cache aus bereits gespeicherten Comps aufgebaut.
- Der Request selbst bleibt dabei schnell; keine SoldComps-/Provider-Abfrage beim normalen Öffnen.
- Das Frontend pollt den Cache während des einmaligen Aufbaus, während Karten und Bilder benutzbar bleiben.
- Nach erfolgreichem manuellen Markt-Refresh wird weiterhin ein vollständiger persistenter Cache gespeichert.

## Erwartetes Verhalten
- Karten/Bilder: sofort bzw. lazy.
- Marktwerte: aus vorhandenem Snapshot in wenigen Sekunden.
- Nur bei einer Legacy-Installation ohne kompatiblen Snapshot: einmaliger Hintergrundaufbau; danach bleiben weitere Seitenaufrufe schnell – auch nach Render-Neustarts, weil der Cache persistent gespeichert wird.

Keine neuen Environment Variables. Keine Provider-Abfrage beim normalen Laden.
