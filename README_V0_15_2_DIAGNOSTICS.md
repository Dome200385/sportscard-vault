# SportsCard Vault V0.15.2 – Supabase Connection Diagnostics

This hotfix prevents a Supabase DNS/connection error from crashing the entire
Render service during startup.

## Changes
- normalizes `SUPABASE_URL` (trims quotes/whitespace and removes accidental paths)
- performs an explicit DNS check for the Supabase hostname
- keeps the API/Scanner online via a clearly reported SQLite diagnostic fallback
- separates database and Storage diagnostics
- extends `/api/v1/system/persistence-check` with requested/active provider,
  normalized URL, hostname, DNS status, bucket status and exact errors
- makes Storage upload failures non-fatal while diagnostics are in progress

## Expected next test
After deploy, open:
`/api/v1/system/persistence-check`

Do **not** start mass collection until `ready_for_mass_collection` is `true`.
