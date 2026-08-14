# Fortschritt V0.8

## Erledigt
1. V0.7 auf V0.8 angehoben.
2. Render-Blueprint in die Repository-Wurzel verschoben/neu erstellt.
3. UI wird vom FastAPI-Backend selbst ausgeliefert; dadurch gleiche Origin für UI und API.
4. Produktions-Preflight und Healthcheck beibehalten.
5. `RECOGNITION_PROVIDER=openai` für Render vorbereitet.
6. `OPENAI_API_KEY` als geheime, nicht synchronisierte Render-Variable definiert.
7. OpenAI Vision + Structured Outputs bleiben strikt vom Preis-Modul getrennt.
8. Android-Fotos werden serverseitig per EXIF ausgerichtet und für Vision auf max. 2200 px komprimiert; Original bleibt erhalten.
9. Kleine Schrift/Kartennummern werden durch hohe JPEG-Qualität und `detail=high` priorisiert.
10. Safe-Fallback bleibt aktiv, falls die externe Vision-Analyse fehlschlägt.
11. Sammlung, Scan-Historie, Korrekturprotokoll und Duplicate-Fingerprint bleiben erhalten.
12. Lokale Tests: 10/10 bestanden.

## Bewusste Grenze
Persistenz ist in V0.8 noch nicht produktionsreif: Render nutzt für den Test SQLite unter `/tmp`. Erst nach erfolgreichem Erkennungstest wird auf eine dauerhafte DB umgestellt.

## Danach
- V0.9: echte Karten-Härtetests und Verbesserung der Erkennungsregeln.
- V0.10: persistente Supabase/Postgres-Datenbank + Bildspeicher.
- Danach: Sold-Comps-Provider und Portfolio-Bewertung.
