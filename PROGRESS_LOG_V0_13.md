# SportsCard Vault V0.13 – Save & Collection

## Umgesetzt
- Scan-first bleibt Standard; manuelle Erfassung ist nicht erforderlich.
- Neuer Endpunkt `POST /api/v1/cards/confirm-scan-auto` speichert die erkannten Kartendaten direkt aus dem Scan.
- Kritische Unsicherheiten werden vor dem Speichern abgefangen; nach Sichtprüfung kann mit einem zweiten Klick bewusst trotzdem gespeichert werden.
- Vorder- und Rückseitenpfade werden automatisch dem gespeicherten Exemplar zugeordnet.
- Exakte Kartenidentitäten werden weiterhin wiederverwendet; mehrere physische Exemplare bleiben getrennte Instanzen.
- Die bestehende Korrektur-Speicherung bleibt als sekundäre Option verfügbar.
- Preflight zeigt jetzt ausdrücklich an, ob die Datenbank persistent ist.
- Aktuelles Render-Setup mit `/tmp/sportscards.db` ist nur Testspeicher. Vor der Massenerfassung wird auf Supabase/Postgres umgestellt.
- UI auf V0.13 aktualisiert: `1-Klick speichern` ist der Primärweg.
- 13/13 Backend-Tests bestanden.

## Nächster Entwicklungsblock
1. V0.13 auf GitHub/Render deployen und echten Scan + 1-Klick-Speicherung testen.
2. Supabase/Postgres als dauerhafte Sammlung anbinden.
3. Bildspeicher dauerhaft machen (Supabase Storage oder gleichwertig).
4. Sammlungssuche/Detailansicht und Backup erweitern.
5. Danach erst produktive Massenerfassung starten.
