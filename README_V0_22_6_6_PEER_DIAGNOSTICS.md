# SportsCard Vault V0.22.6.6 – Peer Diagnostics

Diagnostic release on top of V0.22.6.5.

- Keeps verified market values and persistent defensive-estimate storage unchanged.
- Adds the top five peer candidates to every defensive estimate.
- Each diagnostic peer contains player, product/set, card number, verified value, similarity score, matching reasons, multiplier and whether it was accepted into the pricing band.
- Collection cards show the top peer directly below the AI estimate so identical-price causes can be inspected without guessing.
- New method id: `weighted_card_similarity_v6_diagnostic`.

This release is intentionally diagnostic; it does not loosen peer thresholds or invent new prices.
