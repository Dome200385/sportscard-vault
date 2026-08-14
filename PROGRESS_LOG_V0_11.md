# SportsCard Vault V0.11 – Recognition Hotfix

## Behoben
- Kritischer Prompt-Fehler beseitigt: JSON-Beispiel in einem Python-f-String führte zu `ValueError: Invalid format specifier`.
- Prompt-Erzeugung ist jetzt formatierungsfrei und kann JSON-Beispiele sicher enthalten.
- Zusätzliche konservative Regeln für Parallel-/Variation-Erkennung.
- Front-/Back-Mismatch wird als Warnung verlangt.
- Version auf 0.11.0 angehoben.
- Regressionstest ergänzt, damit derselbe Fehler nicht erneut eingeschleppt wird.

## Erwarteter Test
Nach Deployment dieselbe Karte erneut vorne und hinten scannen. Bei Erfolg muss `mode=openai-vision` statt `safe-fallback` erscheinen und erkannte Felder mit Confidence geliefert werden.
