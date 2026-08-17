# SportsCard Vault V0.8

Scan-first Sports-Card-Collection-App für detaillierte Erfassung großer Sammlungen.

## Testfokus dieser Version
Vorder- und Rückseite fotografieren → automatische Vision-Analyse → detaillierte Felder mit Confidence → nur Unsicherheiten korrigieren → speichern.

## Deployment
Siehe `DEPLOY_RENDER.md`.

## Backend-Tests
```bash
cd backend
pip install -r requirements.txt
PYTHONPATH=. python -m pytest -q
```

Aktueller Stand: **10/10 Tests bestanden**.
