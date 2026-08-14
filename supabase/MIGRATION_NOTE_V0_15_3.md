# V0.15.3 schema note

The database was initialized with `supabase/schema.sql`, which is the legacy
V0.1 detailed schema. The current JSON-based persistence provider expects
`schema_v0_14.sql` (`data_json`, `identity_fingerprint`, `scan_corrections`).

V0.15.3 only probes connectivity and reports `postgres_info.schema_family`.
Do not begin mass collection until the schema is aligned and the persistence
check is fully green.
