# SportsCard Vault V0.22.4.5 – Serialized Market Load

Dieser Patch stabilisiert ausschließlich den Frontend-Ladeablauf der Sammlung.

- Der kompakte Collection Feed bleibt unverändert und lädt die Karten sofort.
- Beim normalen Öffnen wird **kein** Performance-Baseline-POST mehr gestartet.
- Der gespeicherte `/api/v1/collection/market-summary` wird als einzelner kontrollierter Request geladen.
- Erst nach erfolgreichem Market Summary wird die Portfolio-Historie nachgeladen.
- Market Summary besitzt einen 30-Sekunden-Timeout und genau einen verzögerten Retry.
- Ein History-Fehler entfernt weder Karten noch bereits geladene Marktwerte.
- Es werden beim normalen Öffnen weiterhin keine SoldComps-Suchen ausgelöst.

Ziel: Karten sofort sichtbar, danach 545.33 USD / 456 gespeicherte Comps nachladen, ohne parallele schwere Requests gegen Render.
