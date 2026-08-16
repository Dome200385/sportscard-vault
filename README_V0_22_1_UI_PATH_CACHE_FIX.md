# SportsCard Vault V0.22.1 – UI Path & Cache Fix

This mini patch places the V0.22 Portfolio Dashboard in the canonical path used by the FastAPI service: `backend/static/index.html`.

It also adds `no-store/no-cache` headers to `/`, `/scan`, and `/app`, preventing an older dashboard from being retained after a Render deploy.

Upload the patch preserving folders, replace existing files, commit, and deploy once.
