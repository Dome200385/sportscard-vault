create extension if not exists "pgcrypto";

create table if not exists public.card_identities (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null,
  sport text not null,
  league text,
  season text,
  release_year int,
  manufacturer text,
  brand text,
  product_line text,
  set_name text,
  subset_name text,
  insert_name text,
  card_number_printed text,
  card_number_normalized text,
  primary_subject_name text not null,
  secondary_subject_names jsonb not null default '[]'::jsonb,
  team_name text,
  parallel_name text,
  variation_name text,
  is_rookie boolean not null default false,
  rookie_label_text text,
  is_insert boolean not null default false,
  is_short_print boolean not null default false,
  is_super_short_print boolean not null default false,
  is_case_hit boolean not null default false,
  is_autograph boolean not null default false,
  autograph_type text,
  is_relic boolean not null default false,
  relic_type text,
  is_rpa boolean not null default false,
  is_serial_numbered boolean not null default false,
  serial_print_run int,
  known_print_run int,
  catalog_key text,
  reference_source text,
  reference_source_id text,
  recognition_status text not null default 'user_confirmed',
  overall_confidence numeric(5,4),
  field_confidences jsonb not null default '{}'::jsonb,
  uncertain_fields jsonb not null default '[]'::jsonb,
  user_corrections jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.card_instances (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null,
  card_identity_id uuid not null references public.card_identities(id) on delete cascade,
  quantity int not null default 1 check (quantity > 0),
  raw_or_graded text not null default 'raw',
  raw_condition text,
  grading_company text,
  grade_numeric numeric(4,2),
  grade_label text,
  subgrades jsonb not null default '{}'::jsonb,
  cert_number text,
  serial_number_actual text,
  autograph_grade text,
  acquired_date date,
  acquired_price numeric(12,2),
  acquired_currency text,
  acquired_from text,
  storage_location text,
  personal_tags jsonb not null default '[]'::jsonb,
  notes text,
  front_image_path text,
  back_image_path text,
  for_sale boolean not null default false,
  asking_price numeric(12,2),
  favorite boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.market_comps (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null,
  card_identity_id uuid not null references public.card_identities(id) on delete cascade,
  source text not null,
  source_item_id text,
  source_url text,
  sale_type text,
  sold_at timestamptz,
  price numeric(12,2) not null,
  currency text not null,
  shipping_price numeric(12,2),
  all_in_price numeric(12,2),
  raw_or_graded text,
  grading_company text,
  grade_numeric numeric(4,2),
  title_raw text,
  matched_identity_confidence numeric(5,4),
  included_in_valuation boolean not null default true,
  exclusion_reason text,
  created_at timestamptz not null default now()
);

create table if not exists public.market_price_snapshots (
  id uuid primary key default gen_random_uuid(),
  card_identity_id uuid not null references public.card_identities(id) on delete cascade,
  data_json jsonb not null default '{}'::jsonb,
  recorded_at timestamptz not null default now()
);

create table if not exists public.scan_events (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null,
  front_image_path text,
  back_image_path text,
  extracted_front_text text,
  extracted_back_text text,
  model_name text,
  model_version text,
  raw_structured_output jsonb,
  candidate_matches jsonb not null default '[]'::jsonb,
  final_card_identity_id uuid references public.card_identities(id) on delete set null,
  created_at timestamptz not null default now()
);

create index if not exists idx_card_identities_user on public.card_identities(owner_user_id);
create index if not exists idx_card_identities_player on public.card_identities(lower(primary_subject_name));
create index if not exists idx_card_identities_sport_season on public.card_identities(sport, season);
create index if not exists idx_card_identities_cardnum on public.card_identities(card_number_normalized);
create index if not exists idx_card_instances_user on public.card_instances(owner_user_id);
create index if not exists idx_card_instances_identity on public.card_instances(card_identity_id);
create index if not exists idx_market_comps_identity on public.market_comps(card_identity_id, sold_at desc);
create index if not exists idx_market_price_snapshots_card_time on public.market_price_snapshots(card_identity_id, recorded_at desc);

alter table public.card_identities enable row level security;
alter table public.card_instances enable row level security;
alter table public.market_comps enable row level security;
alter table public.scan_events enable row level security;

-- Assumes owner_user_id stores auth.uid().
create policy "card identities owner only" on public.card_identities
  for all using (owner_user_id = auth.uid()) with check (owner_user_id = auth.uid());
create policy "card instances owner only" on public.card_instances
  for all using (owner_user_id = auth.uid()) with check (owner_user_id = auth.uid());
create policy "market comps owner only" on public.market_comps
  for all using (owner_user_id = auth.uid()) with check (owner_user_id = auth.uid());
create policy "scan events owner only" on public.scan_events
  for all using (owner_user_id = auth.uid()) with check (owner_user_id = auth.uid());

-- Extra fields planned by V0.1 detailed model can be added without changing owned instances.
-- Production migration will expand card_identities after the first 50-100 real-card acceptance set is frozen.
