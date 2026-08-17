# V0.1 Status

## Implemented now
- Runnable FastAPI backend
- Local SQLite development database (no cloud account required for first test)
- Detailed manual card identity + owned-instance entry
- Collection list/search API with pagination suitable for >4,000 rows
- Duplicate identity counting
- Front/back image upload endpoint
- Safe locked-context recognition scaffold: never invents unknown card fields
- Manual traceable comp entry
- Valuation requires >=3 same-currency included comps; median is used
- CSV export
- Render deployment config + Dockerfile
- Flutter Android shell: collection, detailed manual entry, scanner placeholder
- Automated backend tests

## Next implementation block
1. Real front/back multimodal recognition adapter with strict structured output.
2. Candidate matching against a card reference catalog.
3. Confirmation UI showing field-by-field confidence and parallel alternatives.
4. Supabase production persistence/auth/storage.
5. Pricing-provider adapter after choosing a compliant sold-sales source.

## Non-negotiable quality rule
No price without source evidence, and no uncertain parallel silently saved.
