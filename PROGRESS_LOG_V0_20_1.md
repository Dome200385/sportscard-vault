# V0.20.1 Progress

- Confirmed V0.20.0 single-card SoldComps refresh returns HTTP 200 and stores verified comps.
- Root cause for collection UI failure: bulk refresh performed external SoldComps calls sequentially, risking browser/proxy request timeout.
- Implemented unique-query grouping + bounded parallel SoldComps fetches.
- Preserved one API credit per unique query.
- Improved collection UI error reporting and recovery.
