create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  nickname text check (char_length(nickname) between 1 and 50),
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.plant_species (
  id uuid primary key default gen_random_uuid(),
  common_name_ko text not null,
  common_name_en text,
  scientific_name text,
  light_level text,
  light_min_lux integer check (light_min_lux is null or light_min_lux >= 0),
  light_max_lux integer check (light_max_lux is null or light_max_lux >= light_min_lux),
  light_hours_min numeric(4, 1) check (light_hours_min is null or light_hours_min between 0 and 24),
  light_hours_max numeric(4, 1) check (
    light_hours_max is null or light_hours_max between light_hours_min and 24
  ),
  soil_moisture_min numeric(5, 2) check (
    soil_moisture_min is null or soil_moisture_min between 0 and 100
  ),
  soil_moisture_max numeric(5, 2) check (
    soil_moisture_max is null or soil_moisture_max between soil_moisture_min and 100
  ),
  watering_interval_min_days integer check (
    watering_interval_min_days is null or watering_interval_min_days > 0
  ),
  watering_interval_max_days integer check (
    watering_interval_max_days is null
    or watering_interval_max_days >= watering_interval_min_days
  ),
  temperature_min_c numeric(4, 1),
  temperature_max_c numeric(4, 1) check (
    temperature_max_c is null or temperature_max_c >= temperature_min_c
  ),
  humidity_min_percent numeric(5, 2) check (
    humidity_min_percent is null or humidity_min_percent between 0 and 100
  ),
  humidity_max_percent numeric(5, 2) check (
    humidity_max_percent is null or humidity_max_percent between humidity_min_percent and 100
  ),
  difficulty text check (difficulty in ('easy', 'medium', 'hard')),
  toxicity text,
  care_notes text,
  extra_care jsonb not null default '{}'::jsonb check (jsonb_typeof(extra_care) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (scientific_name)
);

create table public.persona_templates (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique check (slug ~ '^[a-z0-9-]+$'),
  name text not null,
  description text,
  personality jsonb not null default '{}'::jsonb check (jsonb_typeof(personality) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.plants (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  species_id uuid references public.plant_species(id) on delete set null,
  persona_template_id uuid references public.persona_templates(id) on delete set null,
  name text not null check (char_length(name) between 1 and 50),
  acquired_at date,
  location text,
  pot_size_cm numeric(5, 1) check (pot_size_cm is null or pot_size_cm > 0),
  personality_overrides jsonb not null default '{}'::jsonb
    check (jsonb_typeof(personality_overrides) = 'object'),
  care_overrides jsonb not null default '{}'::jsonb
    check (jsonb_typeof(care_overrides) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.messages (
  id bigint generated always as identity primary key,
  plant_id uuid not null references public.plants(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null check (char_length(content) between 1 and 4000),
  created_at timestamptz not null default now()
);

create table public.memories (
  id uuid primary key default gen_random_uuid(),
  plant_id uuid not null references public.plants(id) on delete cascade,
  category text not null check (category in ('user', 'plant', 'preference', 'care', 'relationship')),
  content text not null check (char_length(content) between 1 and 500),
  importance smallint not null default 1 check (importance between 1 and 5),
  source_message_id bigint references public.messages(id) on delete set null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.sensor_readings (
  id bigint generated always as identity primary key,
  plant_id uuid not null references public.plants(id) on delete cascade,
  soil_moisture numeric(5, 2) check (soil_moisture is null or soil_moisture between 0 and 100),
  temperature_c numeric(5, 2),
  humidity_percent numeric(5, 2) check (
    humidity_percent is null or humidity_percent between 0 and 100
  ),
  light_lux numeric(12, 2) check (light_lux is null or light_lux >= 0),
  measured_at timestamptz not null default now(),
  check (
    soil_moisture is not null
    or temperature_c is not null
    or humidity_percent is not null
    or light_lux is not null
  )
);

create index plants_user_id_idx on public.plants(user_id);
create index messages_plant_created_idx on public.messages(plant_id, created_at desc);
create index memories_plant_active_idx on public.memories(plant_id, is_active, importance desc);
create index sensor_readings_plant_measured_idx
  on public.sensor_readings(plant_id, measured_at desc);

create trigger profiles_set_updated_at before update on public.profiles
for each row execute function public.set_updated_at();
create trigger plant_species_set_updated_at before update on public.plant_species
for each row execute function public.set_updated_at();
create trigger persona_templates_set_updated_at before update on public.persona_templates
for each row execute function public.set_updated_at();
create trigger plants_set_updated_at before update on public.plants
for each row execute function public.set_updated_at();
create trigger memories_set_updated_at before update on public.memories
for each row execute function public.set_updated_at();

alter table public.profiles enable row level security;
alter table public.plant_species enable row level security;
alter table public.persona_templates enable row level security;
alter table public.plants enable row level security;
alter table public.messages enable row level security;
alter table public.memories enable row level security;
alter table public.sensor_readings enable row level security;

grant select, insert, update, delete on public.profiles to authenticated;
grant select on public.plant_species to authenticated;
grant select on public.persona_templates to authenticated;
grant select, insert, update, delete on public.plants to authenticated;
grant select, insert, update, delete on public.messages to authenticated;
grant select, insert, update, delete on public.memories to authenticated;
grant select, insert, update, delete on public.sensor_readings to authenticated;
grant usage, select on all sequences in schema public to authenticated;

create policy "profiles are private" on public.profiles
for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy "authenticated users can read species" on public.plant_species
for select to authenticated using (true);

create policy "authenticated users can read persona templates" on public.persona_templates
for select to authenticated using (true);

create policy "users own their plants" on public.plants
for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy "users own their plant messages" on public.messages
for all to authenticated
using (exists (
  select 1 from public.plants
  where plants.id = messages.plant_id and plants.user_id = auth.uid()
))
with check (exists (
  select 1 from public.plants
  where plants.id = messages.plant_id and plants.user_id = auth.uid()
));

create policy "users own their plant memories" on public.memories
for all to authenticated
using (exists (
  select 1 from public.plants
  where plants.id = memories.plant_id and plants.user_id = auth.uid()
))
with check (exists (
  select 1 from public.plants
  where plants.id = memories.plant_id and plants.user_id = auth.uid()
));

create policy "users own their sensor readings" on public.sensor_readings
for all to authenticated
using (exists (
  select 1 from public.plants
  where plants.id = sensor_readings.plant_id and plants.user_id = auth.uid()
))
with check (exists (
  select 1 from public.plants
  where plants.id = sensor_readings.plant_id and plants.user_id = auth.uid()
));

insert into public.persona_templates (slug, name, description, personality)
values (
  'warm-friend',
  '다정한 친구',
  '차분하고 다정하게 사용자의 하루를 챙기는 기본 성격',
  '{
    "tone": "따뜻하고 다정한 반말",
    "energy": 3,
    "affection": 4,
    "humor": 2,
    "talk_length": "짧게",
    "traits": ["차분함", "다정함", "호기심이 많음"],
    "favorite_topics": ["사용자의 하루", "햇빛", "식물 돌봄"]
  }'::jsonb
)
on conflict (slug) do nothing;
