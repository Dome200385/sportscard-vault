# SportsCard Vault V0.16.0 – Mobile Web App

V0.16.0 turns the existing backend test page into a usable mobile-first scanner and collection UI.

## New
- `/`, `/scan` and `/app` all open the scanner UI.
- Camera-friendly front/back capture with previews.
- One-tap AI analysis and confirmation flow, including explicit “save despite uncertainty”.
- Collection dashboard with stats, search and card thumbnails loaded from persistent Postgres image storage.
- Card detail modal with front/back images and key metadata.
- API/Swagger remains available under `/docs`.

No new Render environment variables or database migrations are required.
