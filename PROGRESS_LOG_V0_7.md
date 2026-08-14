# SportsCard Vault – Fortschritt bis V0.7

## Zieländerung
Manuelle Erfassung ist **kein normaler Workflow mehr**. Der Primärablauf lautet:
1. Vorderseite fotografieren.
2. Rückseite fotografieren.
3. Vision analysiert beide Bilder.
4. Daten werden strukturiert extrahiert.
5. Nur unsichere Angaben werden korrigiert/bestätigt.
6. Karte wird gespeichert.

## Erledigt
- Scan-first Weboberfläche statt Formular-first.
- Front/Back-Kamera-Upload.
- Fast-Scan-Kontext optional für Boxen/gleiche Sets.
- Feldweise Confidence + Evidence.
- Parallel und Variation bleiben eigenständige, konservativ behandelte Felder.
- Seriennummer trennt Exemplar-Nummer (17/99) und Print Run (/99).
- Grading Company, Grade und Cert separat.
- Deterministischer Zweitpass gegen bereits bekannte Karten/Katalogdaten.
- Korrekturen bleiben als Lern-/Auditdaten gespeichert.
- Preflight-Systemstatus zeigt, ob echte Vision-Erkennung aktiv ist.
- Keine KI-Preisfantasie: Pricing bleibt vollständig getrennt.
- Collection Summary und CSV-Export bleiben vorhanden.
- 10 automatisierte Tests.

## Bewusst noch nicht automatisch
- Sold-Comps: eBay Browse liefert aktuelle kaufbare Listings, keine frei verfügbare vollständige Sold-Historie. Deshalb wird kein Listing-Preis als echter Marktwert ausgegeben.
- Vollständiger globaler Kartenkatalog: wird als austauschbarer Catalog Provider vorgesehen.
- Native APK: Flutter/Android SDK sind in der Build-Umgebung nicht vorhanden. Web/PWA bleibt bis zum Android-Build die Testoberfläche.

## Nächste technische Stufe
- Supabase persistent aktivieren.
- Vision-Key im Backend setzen.
- 20 echte Karten als Benchmark scannen.
- Fehlerquote getrennt messen: Spieler, Set, Nummer, Parallel, Variation.
- Danach erst Massenscan und Preisprovider produktiv schalten.
