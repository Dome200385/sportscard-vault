# SportsCard Vault V0.22.4.6 – Market-first / Image Throttle

This patch keeps the fast collection feed, but changes the browser load order:

- cards/text render immediately;
- card thumbnail image reads are temporarily deferred;
- persisted `/api/v1/collection/market-summary` loads first;
- market values are applied to the UI;
- thumbnails are then loaded in batches of 2;
- portfolio history loads last;
- if market loading fails, the exact HTTP/timeout diagnosis is displayed in the collection value card.

No SoldComps/provider request is triggered by opening the collection.
No database migration or new environment variable is required.
