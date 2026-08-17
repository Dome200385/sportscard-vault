# SportsCard Vault V0.22.4.12

Hotfix fuer den Marktcache-HTTP-500 aus V0.22.4.11.

Fehlerursache:
`app.db` exportierte die bereits in den DB-Providern vorhandenen Methoden
`add_collection_market_snapshot` und `list_collection_market_snapshots` nicht.

Fix:
- DB-Facade exportiert Collection-Market-Snapshot Methoden.
- Keine Aenderung an Karten, Bildern oder gespeicherten Comps.
- Marktcache-Rebuild aus V0.22.4.11 kann danach persistent speichern.
- Versionsanzeige auf V0.22.4.12.

Deployment: Inhalt dieses ZIPs mit gleicher Ordnerstruktur ins Repository uebernehmen und deployen.
