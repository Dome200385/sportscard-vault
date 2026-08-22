# SportsCard Vault V0.24.0 — Multi-Source Market Engine

## Ziel
V0.24.0 trennt drei Preis-Signale strikt voneinander:

1. **Verifizierte Verkäufe (SoldComps Sold)** — einzige automatische Quelle für echten Marktwert, Portfolio-Wert und Historie.
2. **Aktive Angebote (SoldComps Active)** — separater Angebotsmarkt-Indikator; niemals als Verkaufspreis oder Sammlungswert gespeichert.
3. **Defensive KI-Schätzung** — bleibt separat und wird nicht durch Angebotspreise ersetzt.

## Neu
- Neuer Provider-Call mit `sold=false` für aktive eBay-Angebote.
- Strenges Karten-Matching bleibt auch bei aktiven Angeboten aktiv.
- Anzeige pro Karte: Median-Angebot, Spanne und Anzahl gematchter aktiver Listings.
- Neuer Button **„Angebotsmarkt prüfen“** für bis zu 12 Karten pro Lauf.
- Neue Endpoints:
  - `POST /api/v1/cards/{card_id}/market/active-refresh`
  - `POST /api/v1/collection/market/active-refresh`
  - `GET /api/v1/collection/market/active-summary`
- Separater Health-State für Sold-Listings und Active-Listings.
- Angebotsmarkt beeinflusst **nicht**:
  - verifizierten Marktwert
  - Sammlungsgesamtwert
  - Marktperformance / Historie
  - gespeicherte SoldComps

## Provider-Ausfall
Die V0.23.0 Retry-/Backoff-Logik bleibt erhalten. Wenn Sold-Listings instabil sind, kann der aktive Angebotsmarkt separat geprüft werden, ohne bestehende Preise zu beschädigen.

## Test
- Backend: 16/16 bestehende Tests bestanden.
- Python-Compile erfolgreich.
- Frontend-JavaScript Syntax geprüft.
- Active-Listing-Normalisierung mit strengem Identitätsmatch separat geprüft.
