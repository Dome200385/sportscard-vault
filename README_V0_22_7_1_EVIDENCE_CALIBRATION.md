# SportsCard Vault V0.22.7.1 – Evidence Calibration

V0.22.7.1 keeps the card-specific differentiation introduced by V0.22.7.0, but adds an evidence-aware final calibration layer for defensive estimates.

- Verified SoldComps remain authoritative and are never altered.
- Strong verified peers permit larger premiums.
- Weak soft-peer estimates require stronger evidence before moving many multiples above their category anchor.
- Feature evidence, empirical factors, similarity score, peer count and print-run evidence affect the calibration envelope.
- Excess above the evidence envelope is compressed, not hard-clipped, preserving card-specific differences.
- Each estimate now stores `confidence_score`, `pre_calibration_estimate`, `calibration_limit`, and `calibration_applied`.
- The UI shows the numeric evidence confidence next to the label.
