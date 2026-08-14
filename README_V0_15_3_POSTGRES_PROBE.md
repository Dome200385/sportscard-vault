# SportsCard Vault V0.15.3 – Native Postgres Probe

Adds a non-destructive native Postgres connection diagnostic through
`SUPABASE_DATABASE_URL`. No card data is migrated or written by this probe.

The persistence endpoint reports DNS, connection status, and the detected
SportsCard schema family.

For IPv4-only hosting, use the Supabase **Supavisor Session pooler** connection
string. The Direct connection endpoint is IPv6 unless the Supabase IPv4 add-on
is enabled.
