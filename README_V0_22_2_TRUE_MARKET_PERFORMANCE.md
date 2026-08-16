# SportsCard Vault V0.22.2 – True Market Performance

V0.22.2 trennt die Entwicklung des Sammlungswerts von echter Marktperformance.

- Portfolio-Snapshots speichern ab jetzt die bewerteten Kartenpositionen mit ihrem jeweiligen Marktwert.
- Ein einmaliger Performance-Baseline-Snapshot wird beim ersten Laden der Sammlung automatisch angelegt, ohne SoldComps-API-Request.
- Zugänge erhöhen den Sammlungswert, werden aber nicht als Marktgewinn gezählt.
- Abgänge reduzieren den Sammlungswert, werden aber nicht als Marktverlust gezählt.
- Marktperformance misst nur Preisänderungen von Karten, die zwischen zwei Snapshots im Bestand geblieben sind.
- 7T / 30T / 90T / 1J zeigen die bestandsbereinigte Marktperformance.
- Die historische Gesamtwert-Grafik bleibt unverändert erhalten, damit die tatsächliche Größe der Sammlung langfristig nachvollziehbar bleibt.
- Manuelle Löschung bleibt unverändert; keine automatische Dublettenlöschung.

Wichtig: Historische Snapshots vor V0.22.2 besitzen keine Positionsdaten. Die bestandsbereinigte Performance beginnt deshalb mit der automatisch angelegten V0.22.2-Baseline. Die ältere Gesamtwert-Historie bleibt vollständig sichtbar.
