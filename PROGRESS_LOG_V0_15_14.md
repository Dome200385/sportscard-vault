# V0.15.14

- Fixed false-positive Postgres image persistence readiness.
- Added fresh-connection verification after image writes.
- Hardened image lookup for `pgimg://` and bare UUID references.
- Added real persistence probe to diagnostics.
