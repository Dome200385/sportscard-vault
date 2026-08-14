# SportsCard Vault – V0.2 Status

## Fertig
- Front-/Rückseiten-Scan-Endpunkt mit austauschbarem Recognition Provider
- Safe Mode: erfindet keine Kartendetails, wenn kein Vision Provider konfiguriert ist
- OpenAI-Vision-Adapter mit strukturierter Ausgabe für detaillierte Kartenfelder
- Harte Confidence-Schwellen, besonders für Parallel/Variation/Seriennummer
- Nutzer-Locks für Fast Scan (Sport/Saison/Produkt etc.) werden nie überschrieben
- Eigene Instance-Erkennung für Slab/Grading/Cert/konkrete Seriennummer
- Keine Preis- oder Marktwertfelder in der KI-Erkennung
- Kandidatenliste für echte Mehrdeutigkeiten
- Flutter-Scanner: Vorderseite, Rückseite, Fast-Scan-Kontext, Confidence-Review
- Backend Regression Tests

## Sicherheitsregeln
1. Parallel/Variation wird bei Unsicherheit nicht automatisch akzeptiert.
2. Preisermittlung bleibt vollständig getrennt von Bilderkennung.
3. KI darf keine Marktwerte erzeugen.
4. Eine Karte wird erst nach Bestätigung in die Collection übernommen.
5. Locked Context gilt als Nutzer-Fakt und hat Vorrang vor KI-Ausgabe.

## Nächster Ausbau V0.3
- Editierbarer Bestätigungsbildschirm für alle erkannten Felder
- Candidate Picker bei Parallel-/Variation-Ambiguität
- Direkter Confirm-and-Save Flow aus dem Scanner
- Supabase-Repository als Cloud-Datenbank
- Auth + Collection Sync
- Scan-History und Korrekturprotokoll als Lernbasis
