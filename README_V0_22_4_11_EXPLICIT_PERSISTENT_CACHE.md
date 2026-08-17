# SportsCard Vault V0.22.4.11 — Explicit Persistent Market Cache

## Ziel
Normales Öffnen der Sammlung führt **keine** Sammlung-weite Marktberechnung mehr aus.

## Neu
- `GET /api/v1/collection/market-cache` ist strikt read-only und liest nur persistierte Snapshots.
- `GET /api/v1/collection/market-summary` ist nur noch ein kompatibler Alias auf denselben schnellen Cache.
- Kein automatischer Cache-Bootstrap beim Öffnen der Sammlung.
- Neuer einmaliger Migrations-Endpunkt `POST /api/v1/collection/market-cache/rebuild`.
  - nutzt nur bereits gespeicherte Comps
  - keine SoldComps-/Provider-Abfragen
  - speichert danach eine vollständige `market_summary_cache` im Portfolio-Snapshot.
- Wenn noch kein Vollcache vorhanden ist, zeigt die Sammlung einen Button **Marktcache initialisieren** statt im Hintergrund minutenlang zu rechnen.
- Der explizite Button **Marktdaten aktualisieren** bleibt der normale Weg für spätere Marktupdates; nach erfolgreichem Refresh wird der fertige Snapshot weiterhin persistent gespeichert.

## Erwarteter Ablauf nach Deploy
1. Sammlung öffnen: Karten/Bilder sofort.
2. Falls Cache bereits vorhanden: Gesamtwert/Comps praktisch sofort.
3. Falls Legacy-Daten ohne Vollcache: einmalig **Marktcache initialisieren** drücken und warten.
4. Danach Seite neu laden: Marktwerte kommen aus dem gespeicherten Cache ohne Neuberechnung.

Keine neue Environment Variable und keine DB-Migration erforderlich.
