# Entwicklungslog V0.5

## 1 – V0.2 übernommen und Regression geprüft
- Bestehendes FastAPI/Flutter-Grundgerüst übernommen.
- Aktuellen Backendstand erneut getestet.

## 2 – V0.3/V0.4-Funktionen konsolidiert
- Editierbarer Confirm-and-Save-Flow.
- Scan-History.
- Korrekturprotokoll als Lernbasis.
- Offline-first Testoberfläche.
- Collection Summary.

## 3 – Datenmodell für mehrere Exemplare korrigiert
- Exakte Kartenidentität wird per stabilem Fingerprint erkannt.
- Mehrere identische physische Exemplare verwenden jetzt dieselbe Kartenidentität und getrennte Owned Instances.
- Duplicate Count zählt die tatsächlich vorhandene Menge.

## 4 – Vision Structured Output gehärtet
- Striktes, typisiertes JSON-Schema pro Feld.
- Unbekannte Werte = null.
- Parallel/Variation behalten hohe Confidence-Schwellen.
- Candidate Overrides werden sicher als JSON-Text übertragen und serverseitig normalisiert.
- Keine Preisfelder im Vision-Schema.

## 5 – Preislogik unverändert streng
- Unter drei passenden Comps kein Median-Marktwert.
- Gemischte Währungen werden nicht zu einem Wert vermischt.
- Kein KI-generierter Preis.

## 6 – Direkt testbarer Android-Browser-Build
- Single-file Offline-App erzeugt.
- Kamera-/Galerieauswahl für Vorder-/Rückseite.
- Detaillierte Kartenerfassung.
- Demo-Daten.
- Suche, Bearbeiten, Löschen, Backup, CSV-Export.

## 7 – Tests
- Backend: 9/9 automatisierte Tests bestanden.
- Zusätzlicher Test für Wiederverwendung identischer Kartenidentitäten eingebaut.
