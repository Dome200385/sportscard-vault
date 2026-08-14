# SportsCard Vault V0.10

## Ziel
Erste echte Kartenidentifikation stabilisieren und Fehler nicht mehr still in den Safe-Modus verschlucken.

## Änderungen
- Vision-Modell auf GPT-5.6 angehoben.
- Bei GPT-5.6 wird Bilddetail `original` verwendet, damit kleine Kartennummern, Copyright-Zeilen, Serial Numbers und feine Parallel-Merkmale besser erhalten bleiben.
- Falls der OpenAI-Aufruf scheitert, wird die technische Fehlermeldung (ohne API-Key) in der Scan-Warnung angezeigt.
- Preflight zeigt jetzt auch das aktive Vision-Modell.
- Root-Weboberfläche auf V0.10 aktualisiert.

## Warum
V0.9 konnte Bilder an das Backend senden, aber bei einem Provider-/Schema-/Modellfehler fiel das Backend still auf den Safe-Modus zurück. Dadurch sah es aus, als könne die Karte einfach nicht identifiziert werden. V0.10 macht den eigentlichen Fehler sichtbar und erhöht gleichzeitig die Bildanalysequalität.
