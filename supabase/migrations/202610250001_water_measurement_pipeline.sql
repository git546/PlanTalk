-- Hardware-ready persistence for the deterministic water-balance pipeline.
-- Apply after 202610030001_initial_plantalk_schema.sql.

create table public.measurement_devices (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  external_device_id text not null check (char_length(external_device_id) between 1 and 100),
  name text not null check (char_length(name) between 1 and 100),
  hardware_model text,
  firmware_version text,
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, external_device_id)
);

create table public.plant_water_calibrations (
  id uuid primary key default gen_random_uuid(),
  plant_id uuid not null references public.plants(id) on delete cascade,
  setup_weight_g numeric(12, 3) not null check (setup_weight_g > 0),
  target_wet_weight_g numeric(12, 3) not null check (target_wet_weight_g > 0),
  watering_trigger_weight_g numeric(12, 3) not null check (watering_trigger_weight_g > 0),
  max_single_watering_ml numeric(12, 3) check (
    max_single_watering_ml is null or max_single_watering_ml > 0
  ),
  calibration_version integer not null default 1 check (calibration_version > 0),
  is_active boolean not null default true,
  calibrated_at timestamptz not null default now(),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (watering_trigger_weight_g < target_wet_weight_g),
  unique (plant_id, calibration_version)
);

create table public.weight_measurements (
  id bigint generated always as identity primary key,
  plant_id uuid not null references public.plants(id) on delete cascade,
  device_id uuid references public.measurement_devices(id) on delete restrict,
  calibration_id uuid references public.plant_water_calibrations(id) on delete set null,
  source text not null check (source in ('manual', 'simulator', 'device')),
  weight_g numeric(12, 3) not null check (weight_g > 0),
  raw_sensor_value numeric,
  sequence_no bigint check (sequence_no is null or sequence_no >= 0),
  is_stable boolean not null default true,
  sample_count integer check (sample_count is null or sample_count > 0),
  firmware_version text,
  temperature_c numeric(5, 2),
  humidity_percent numeric(5, 2) check (
    humidity_percent is null or humidity_percent between 0 and 100
  ),
  light_lux numeric(12, 2) check (light_lux is null or light_lux >= 0),
  light_ppfd numeric(12, 3) check (light_ppfd is null or light_ppfd >= 0),
  measured_at timestamptz not null,
  received_at timestamptz not null default now(),
  raw_payload jsonb not null default '{}'::jsonb check (jsonb_typeof(raw_payload) = 'object'),
  check (source <> 'device' or device_id is not null)
);

create table public.care_events (
  id bigint generated always as identity primary key,
  plant_id uuid not null references public.plants(id) on delete cascade,
  device_id uuid references public.measurement_devices(id) on delete restrict,
  event_type text not null check (
    event_type in ('watering', 'drainage', 'calibration', 'setup_changed')
  ),
  source text not null check (source in ('manual', 'simulator', 'device')),
  volume_ml numeric(12, 3) check (volume_ml is null or volume_ml >= 0),
  weight_g numeric(12, 3) check (weight_g is null or weight_g > 0),
  external_event_id text,
  occurred_at timestamptz not null,
  received_at timestamptz not null default now(),
  notes text,
  raw_payload jsonb not null default '{}'::jsonb check (jsonb_typeof(raw_payload) = 'object'),
  check (source <> 'device' or device_id is not null),
  check (
    event_type in ('calibration', 'setup_changed')
    or volume_ml is not null
    or weight_g is not null
  )
);

create index measurement_devices_user_idx
  on public.measurement_devices(user_id, updated_at desc);
create unique index plant_water_calibrations_one_active_idx
  on public.plant_water_calibrations(plant_id) where is_active;
create index plant_water_calibrations_plant_idx
  on public.plant_water_calibrations(plant_id, calibrated_at desc);
create index weight_measurements_plant_measured_idx
  on public.weight_measurements(plant_id, measured_at desc);
create unique index weight_measurements_device_sequence_idx
  on public.weight_measurements(device_id, sequence_no)
  where device_id is not null and sequence_no is not null;
create index care_events_plant_occurred_idx
  on public.care_events(plant_id, occurred_at desc);
create unique index care_events_device_external_idx
  on public.care_events(device_id, external_event_id)
  where device_id is not null and external_event_id is not null;

create trigger measurement_devices_set_updated_at
before update on public.measurement_devices
for each row execute function public.set_updated_at();
create trigger plant_water_calibrations_set_updated_at
before update on public.plant_water_calibrations
for each row execute function public.set_updated_at();

alter table public.measurement_devices enable row level security;
alter table public.plant_water_calibrations enable row level security;
alter table public.weight_measurements enable row level security;
alter table public.care_events enable row level security;

grant select, insert, update, delete on public.measurement_devices to authenticated;
grant select, insert, update, delete on public.plant_water_calibrations to authenticated;
grant select, insert, update, delete on public.weight_measurements to authenticated;
grant select, insert, update, delete on public.care_events to authenticated;
grant usage, select on all sequences in schema public to authenticated;

create policy "users own their measurement devices" on public.measurement_devices
for all to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

create policy "users own their plant water calibrations" on public.plant_water_calibrations
for all to authenticated
using (exists (
  select 1 from public.plants
  where plants.id = plant_water_calibrations.plant_id
    and plants.user_id = auth.uid()
))
with check (exists (
  select 1 from public.plants
  where plants.id = plant_water_calibrations.plant_id
    and plants.user_id = auth.uid()
));

create policy "users own their weight measurements" on public.weight_measurements
for all to authenticated
using (exists (
  select 1 from public.plants
  where plants.id = weight_measurements.plant_id
    and plants.user_id = auth.uid()
))
with check (exists (
  select 1 from public.plants
  where plants.id = weight_measurements.plant_id
    and plants.user_id = auth.uid()
));

create policy "users own their care events" on public.care_events
for all to authenticated
using (exists (
  select 1 from public.plants
  where plants.id = care_events.plant_id
    and plants.user_id = auth.uid()
))
with check (exists (
  select 1 from public.plants
  where plants.id = care_events.plant_id
    and plants.user_id = auth.uid()
));
