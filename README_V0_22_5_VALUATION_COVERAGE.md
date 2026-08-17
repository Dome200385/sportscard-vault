# SportsCard Vault V0.22.5 — Valuation Coverage Upgrade

## Ziel
Die bestehende schnelle Sammlung und der persistente Marktcache bleiben unverändert. V0.22.5 ergänzt eine gezielte zweite SoldComps-Suche nur für Karten, die noch keinen Marktwert haben.

## Neu
- Button **Abdeckung verbessern (N)** erscheint nur, wenn Karten ohne Marktwert vorhanden sind.
- Bereits bewertete Karten werden bei diesem Lauf nicht erneut abgefragt.
- Maximal 20 zusätzliche Provider-Abfragen pro Lauf (API-Kontingent wird geschont).
- Die Fallback-Suche ist breiter als die normale exakte Suche, aber jeder Treffer muss weiterhin den lokalen Identitäts-Matcher bestehen.
- Nur abgeschlossene Verkäufe werden verwendet. Keine Angebotspreise und keine KI-erfundenen Preise.
- Bei nummerierten Parallels darf eine exakt passende Seriennummer (z.B. 23/99) den fehlenden Marketingnamen des Parallels im Verkaufstitel ersetzen, sofern Spieler und Kartennummer exakt passen.
- Erfolgreiche neue Bewertungen werden in den persistenten Marktcache und die Portfolio-Historie übernommen.

## Unverändert
- Manuelle Löschung von Duplikaten.
- Schneller Collection Feed / Lazy Images.
- Persistenter Marktcache.
- Normale Schaltfläche **Marktdaten aktualisieren**.

## Deployment
Ordnerstruktur beibehalten und `backend/` in das bestehende GitHub-Repository hochladen/ersetzen. Danach Render deployen. Keine neuen Environment-Variablen und keine DB-Migration nötig.
