# SportsCard Vault V0.22.4.14 – Image Rehydration Hotfix

V0.22.4.14 keeps the working V0.22.4.13 persistent market-cache architecture unchanged and fixes the confirmed UI regression where card images disappeared after a market refresh.

## Fix
- Every `renderCollection()` pass now automatically restarts lazy thumbnail hydration.
- This covers initial load, market refresh, cache load, filtering, sorting and pagination.
- Image loading remains independent of market data and uses small 2-image batches.
- Existing cards, images, comps, snapshots and market values are not modified.

No database migration or new environment variable is required.
