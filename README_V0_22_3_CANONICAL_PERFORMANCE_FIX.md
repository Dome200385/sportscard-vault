# SportsCard Vault V0.22.3 – Canonical Performance Fix

- Deploys the True Market Performance code to the canonical paths actually served by Render:
  - `backend/app/main.py`
  - `backend/static/index.html`
- Keeps high-value cards untouched. A high market value alone is not treated as suspicious.
- On first load, the current holdings become the performance baseline without a SoldComps request.
- Future card additions/removals change collection value but not market performance.
- Historical total collection-value chart remains intact.
- Manual duplicate deletion remains manual.

## Upload
Drag the **backend folder itself** into GitHub so the paths remain `backend/app/...` and `backend/static/...`.
