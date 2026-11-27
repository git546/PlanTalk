-- Latest sensor assessment and the baseline that produced it, per plant.
create table if not exists public.plant_water_assessments (
  plant_id uuid primary key references public.plants(id) on delete cascade,
  device_id uuid not null references public.measurement_devices(id) on delete cascade,
  measured_at timestamptz not null,
  evaluated_at timestamptz not null,
  observation_status text not null check (
    observation_status in ('recent', 'stale', 'interrupted')
  ),
  summary jsonb not null check (jsonb_typeof(summary) = 'object'),
  check (measured_at <= evaluated_at)
);

alter table public.plant_water_assessments enable row level security;
revoke all on public.plant_water_assessments from public, anon, authenticated;
grant select, insert, update on public.plant_water_assessments to authenticated;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'plant_water_assessments'
      and policyname = 'users own their plant water assessments'
  ) then
    create policy "users own their plant water assessments"
    on public.plant_water_assessments
    for all to authenticated
    using (
      exists (
        select 1 from public.plants p
        where p.id = plant_water_assessments.plant_id and p.user_id = (select auth.uid())
      )
    )
    with check (
      exists (
        select 1 from public.plants p
        where p.id = plant_water_assessments.plant_id and p.user_id = (select auth.uid())
      )
      and exists (
        select 1 from public.measurement_devices d
        where d.id = plant_water_assessments.device_id and d.user_id = (select auth.uid())
      )
    );
  end if;
end;
$$;

create or replace function public.save_plant_water_assessment(
  p_plant_id uuid,
  p_device_id uuid,
  p_measured_at timestamptz,
  p_evaluated_at timestamptz,
  p_observation_status text,
  p_summary jsonb
)
returns void
language sql
security invoker
set search_path = ''
as $$
  insert into public.plant_water_assessments as saved (
    plant_id, device_id, measured_at, evaluated_at, observation_status, summary
  )
  values (
    p_plant_id, p_device_id, p_measured_at, p_evaluated_at, p_observation_status, p_summary
  )
  on conflict (plant_id) do update set
    device_id = excluded.device_id,
    measured_at = excluded.measured_at,
    evaluated_at = excluded.evaluated_at,
    observation_status = excluded.observation_status,
    summary = excluded.summary
  where (excluded.measured_at, excluded.evaluated_at) > (saved.measured_at, saved.evaluated_at);
$$;

revoke execute on function public.save_plant_water_assessment(
  uuid, uuid, timestamptz, timestamptz, text, jsonb
) from public, anon, authenticated;
grant execute on function public.save_plant_water_assessment(
  uuid, uuid, timestamptz, timestamptz, text, jsonb
) to authenticated;
