# Morgen-Test – 10 Minuten

1. `SportsCard_Vault_V0_5_Offline_Test.html` auf dem Android-Gerät öffnen.
2. Unter **Daten** auf **Demo-Karten laden** tippen und Sammlung/Filter prüfen.
3. Unter **Erfassen** eine echte Karte mit möglichst vielen Details manuell anlegen.
4. Prüfen: Parallel, Variation, Print Run und tatsächliche Seriennummer sind getrennte Felder.
5. Drei echte Vergleichsverkäufe eintragen. Erst dann erscheint ein Median-Marktwert.
6. Unter **Scanner** Vorder- und Rückseite fotografieren. Die Offline-Version führt durch die Bestätigungsmaske, rät aber keine Kartendaten.
7. Eine Karte bearbeiten und Lagerort/Tags ergänzen.
8. JSON-Backup und CSV-Export testen.
9. Notieren, welche Felder oder Klicks im Alltag zu langsam/unübersichtlich sind.

## Was noch nicht produktiv ist
- Echte KI-Erkennung benötigt das Backend plus API-Schlüssel.
- Automatische Sold-Comps sind noch nicht angebunden; bis eine verlässliche Quelle feststeht, werden keine Fantasiepreise erzeugt.
- Cloud-Sync/Supabase ist vorbereitet, aber ohne deine Kontozugangsdaten nicht eigenständig aktivierbar.
- Eine native APK kann in dieser Umgebung nicht seriös gebaut werden, weil Flutter/Android SDK hier nicht installiert sind. Die Offline-HTML ist deshalb der direkte Testbuild.
