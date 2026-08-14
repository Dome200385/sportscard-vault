-- SportsCard Vault V0.14 persistent schema
-- Run once in Supabase > SQL Editor before setting DATABASE_PROVIDER=supabase.
-- This is a single-user/backend-only phase. RLS is enabled with no browser
-- policies; the Render backend uses a Supabase secret key server-side.

create extension if not exists "pgcrypto";

create table if not exists public.card_identities (
  id uuid primary key default gen_random_uuid(),
  data_json jsonb not null,
  sport text not null,
  season text,
  primary_subject_name text not null,
  card_number_normalized text,
  product_line text,
  set_name text,
  parallel_name text,
  identity_fingerprint text not null unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.card_instances (
  id uuid primary key default gen_random_uuid(),
  card_identity_id uuid not null references public.card_identities(id) on delete cascade,
  data_json jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.market_comps (
  id uuid primary key default gen_random_uuid(),
  card_identity_id uuid not null references public.card_identities(id) on delete cascade,
  data_json jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists public.scan_events (
  id uuid primary key default gen_random_uuid(),
  front_image_path text,
  back_image_path text,
  locked_context_json jsonb not null default '{}'::jsonb,
  raw_structured_output_json jsonb not null default '{}'::jsonb,
  final_card_identity_id uuid references public.card_identities(id) on delete set null,
  status text not null default 'analyzed',
  created_at timestamptz not null default now(),
  finalized_at timestamptz
);

create table if not exists public.scan_corrections (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references public.scan_events(id) on delete cascade,
  field_name text not null,
  suggested_json jsonb,
  final_json jsonb,
  correction_type text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_identity_search on public.card_identities(sport, season, lower(primary_subject_name), card_number_normalized);
create index if not exists idx_identity_fingerprint on public.card_identities(identity_fingerprint);
create index if not exists idx_instances_identity on public.card_instances(card_identity_id);
create index if not exists idx_comps_identity on public.market_comps(card_identity_id);
create index if not exists idx_scan_created on public.scan_events(created_at desc);
create index if not exists idx_scan_corrections_scan on public.scan_corrections(scan_id);

alter table public.card_identities enable row level security;
alter table public.card_instances enable row level security;
alter table public.market_comps enable row level security;
alter table public.scan_events enable row level security;
alter table public.scan_corrections enable row level security;

-- No anon/authenticated policies are intentionally created in V0.14.
-- The browser talks only to FastAPI; the server secret key bypasses RLS.
