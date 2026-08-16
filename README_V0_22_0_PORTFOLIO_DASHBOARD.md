# SportsCard Vault V0.22.0 — Portfolio Dashboard

## Neu
- Desktop-Dashboard im gewünschten Dark-Portfolio-Look mit linker Navigation.
- Gesamtwert-Chart mit 7T / 30T / 90T / 1J / MAX.
- Portfolio-Zusammenfassung mit Anfangswert, Hoch, Tief und Gesamtveränderung.
- Sechs Kennzahlen: Karten, Datensätze, Comps, Ø Comps/Karte, höchster und niedrigster Einzelwert.
- Kartenkacheln zeigen Marktwert, 30T-Trend und Sparkline.
- Mobile Scan-/Sammlungsnavigation bleibt erhalten.
- Karten werden weiterhin ausschließlich manuell gelöscht; es gibt keine automatische Dublettenlöschung.

## Langfristige Historie
V0.22.0 führt `collection_market_snapshots` ein. Jeder erfolgreiche Sammlungs-Marktrefresh speichert einen unveränderlichen Portfolio-Snapshot. Auch eine manuelle Löschung erzeugt danach einen Snapshot. Dadurch bleibt die dokumentierte Gesamtwertentwicklung langfristig nachvollziehbar.

Installationen von V0.21 werden beim ersten Start automatisch migriert. Frühere Karten-Preis-Snapshots werden im Portfolio-Chart als Legacy-Backfill weiterverwendet, bis genügend echte Portfolio-Snapshots vorhanden sind.

## Deployment
Keine neuen Environment Variables. Patch in das bestehende Repository hochladen und vorhandene Dateien ersetzen, dann Render deployen.
