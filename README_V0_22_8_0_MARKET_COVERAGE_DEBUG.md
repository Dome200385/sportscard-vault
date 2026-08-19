# SportsCard Vault V0.22.8.0 – Market Coverage Debug

This release focuses on real SoldComps coverage for cards that remain without a verified market value.

## What changed
- Coverage search now uses a progressive multi-stage discovery funnel.
- Coverage-only SoldComps searches can look back up to 365 days instead of the normal 90-day refresh window.
- Broader provider queries never loosen local identity verification: player, card number, explicit parallel and grading mismatches still cannot become verified comps.
- The collection stores last-run coverage diagnostics in memory and displays per-card results such as `0 SoldComps-Treffer` or `12 gefunden · verworfen (card_number)`.
- The coverage action uses a 30-request budget and processes cards fairly in round-robin stages.
- Existing verified values, portfolio history, defensive AI estimates and image persistence are unchanged.

## Why
The collection had multiple newly scanned, well-identified cards but no verified values even after both normal refresh and coverage refresh. This version distinguishes provider-discovery failure from local identity rejection and broadens discovery safely.
