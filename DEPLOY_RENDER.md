# SportsCard Vault V0.8 – Render Deployment

## Ziel
Nach dem Deployment **nicht mehr die lokale HTML-Datei öffnen**. Die App wird direkt über die Render-URL aufgerufen, z. B. `https://sportscard-vault-api-xxxx.onrender.com/`. Dadurch laufen Oberfläche und API auf derselben Domain und der Android-Fehler `Failed to fetch` entfällt.

## 1. Projekt in GitHub
- Neues Repository anlegen, z. B. `sportscard-vault`.
- Den **Inhalt dieses Ordners** in die Repository-Wurzel laden.
- Wichtig: `render.yaml` muss direkt in der Repository-Wurzel liegen, nicht nur im Unterordner `backend`.

## 2. OpenAI API-Key vorbereiten
- Einen OpenAI API-Key für die API erzeugen.
- Den Key **niemals** in GitHub, HTML oder Quellcode eintragen.
- Der Key wird ausschließlich als geheime Render-Umgebungsvariable `OPENAI_API_KEY` gespeichert.

## 3. Render Blueprint
- Render Dashboard → **New +** → **Blueprint**.
- GitHub-Repository `sportscard-vault` auswählen.
- Render liest `render.yaml`.
- Beim Setup wird nach `OPENAI_API_KEY` gefragt. Dort den Key eintragen.
- Blueprint anwenden / Service erstellen.

## 4. Deploy prüfen
Nach erfolgreichem Deploy die Render-URL öffnen.

Erwartet auf der Startseite:
- `● Automatische Bilderkennung bereit`
- `openai`

Direkter Healthcheck:
- `/health`

Erwartete JSON-Felder:
- `status: ok`
- `version: 0.8.0`
- `recognition: openai`

Preflight:
- `/api/v1/system/preflight`
- `ready_for_real_scans: true`
- `vision_key_configured: true`

## 5. Erste Testkarte
1. Startseite über die Render-URL öffnen.
2. Vorderseite fotografieren.
3. Rückseite fotografieren.
4. **Analysieren**.
5. Spieler, Saison, Hersteller, Produkt, Set, Kartennummer und besonders Parallel/Variation prüfen.
6. Nur fehlerhafte oder unsichere Details korrigieren.
7. **Bestätigen & speichern**.

## Hinweise zu V0.8
- V0.8 verwendet für den ersten Live-Test noch SQLite im temporären Render-Dateisystem. Die Sammlung ist **noch nicht als dauerhafte Produktionsdatenbank gedacht** und kann bei Deploy/Restart verloren gehen.
- Deshalb zunächst nur Testkarten erfassen. Persistente Cloud-Speicherung ist der nächste Schritt (Supabase/Postgres).
- Marktwerte werden weiterhin nicht von der KI erfunden. Preis-Comps bleiben separat.
