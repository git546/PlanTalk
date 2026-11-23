-- Device and gateway diagnostics that explain gaps in sensor measurements.
-- Apply after 202610250001_water_measurement_pipeline.sql.

create table public.device_diagnostics (
  id bigint generated always as identity primary key,
  device_id uuid not null references public.measurement_devices(id) on delete cascade,
  plant_id uuid references public.plants(id) on delete cascade,
  external_event_id text not null,
  event_type text not null check (char_length(event_type) between 1 and 100),
  severity text not null check (severity in ('info', 'warning', 'error')),
  occurred_at timestamptz not null,
  received_at timestamptz not null default now(),
  details jsonb not null default '{}'::jsonb check (jsonb_typeof(details) = 'object'),
  unique (device_id, external_event_id)
);

create index device_diagnostics_device_time_idx
  on public.device_diagnostics(device_id, occurred_at desc);
create index device_diagnostics_plant_time_idx
  on public.device_diagnostics(plant_id, occurred_at desc)
  where plant_id is not null;

alter table public.device_diagnostics enable row level security;

grant select, insert, update, delete on public.device_diagnostics to authenticated;
grant usage, select on all sequences in schema public to authenticated;

create policy "users own their device diagnostics" on public.device_diagnostics
for all to authenticated
using (exists (
  select 1 from public.measurement_devices
  where measurement_devices.id = device_diagnostics.device_id
    and measurement_devices.user_id = auth.uid()
))
with check (
  exists (
    select 1 from public.measurement_devices
    where measurement_devices.id = device_diagnostics.device_id
      and measurement_devices.user_id = auth.uid()
  )
  and (
    device_diagnostics.plant_id is null
    or exists (
      select 1 from public.plants
      where plants.id = device_diagnostics.plant_id
        and plants.user_id = auth.uid()
    )
  )
);
