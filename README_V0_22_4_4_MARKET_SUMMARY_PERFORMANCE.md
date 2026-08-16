# SportsCard Vault V0.22.4.4 – Lightweight Market Summary

V0.22.4.4 behält den schnellen Collection-Feed aus V0.22.4.x bei und repariert das nachgelagerte Laden der gespeicherten Marktdaten.

## Änderung
- `/api/v1/collection/market-summary` lädt für die Sammlung keine vollständigen Preis-Historien mehr pro Karte.
- Für den aktuellen Marktwert werden nur die bereits gespeicherten Comps verwendet; historische Portfolio-Daten werden weiterhin separat über `/api/v1/collection/market-history` geladen.
- Falls eine Karte nur einen Provider-Snapshot und keine Comps besitzt, wird höchstens der letzte Snapshot gelesen.
- Beim normalen Öffnen der Sammlung gibt es weiterhin **keine SoldComps-Abfrage**.
- Der schnelle `/api/v1/collection/feed` bleibt unverändert.

## Ziel
Karten erscheinen sofort; Gesamtwert, bewertete Karten und gespeicherte Comps werden danach deutlich leichter nachgeladen.
