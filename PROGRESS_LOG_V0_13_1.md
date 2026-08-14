# SportsCard Vault V0.13.1

Hotfix for the V0.13 mobile scan UI.

- Fixed a JavaScript parse error in the uncertainty confirmation dialog. This error prevented all UI event handlers from attaching, which made the Analyze button appear unusable.
- Analyze is now explicitly enabled only after both front and back images are selected.
- Added clear status text before analysis.
- Prevented double taps while an analysis request is running.
- Re-enabled the button automatically after success or failure.
- Bumped API/UI version to 0.13.1.
