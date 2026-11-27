-- Present the two stored sources as one read-only, ownership-filtered timeline.
create or replace view public.plant_watering_records
with (security_invoker = true)
as
select
  p.id as plant_id,
  c.id as source_record_id,
  c.device_id,
  'direct'::text as record_kind,
  c.source,
  c.occurred_at,
  c.volume_ml,
  null::timestamptz as estimated_from_at,
  null::numeric as observed_weight_increase_g
from public.care_events c
join public.plants p on p.id = c.plant_id
where c.event_type = 'watering' and c.source in ('manual', 'device')

union all

select
  p.id as plant_id,
  d.id as source_record_id,
  d.device_id,
  'inferred'::text as record_kind,
  'sensor'::text as source,
  d.occurred_at,
  null::numeric as volume_ml,
  previous.measured_at as estimated_from_at,
  detection.increase_g as observed_weight_increase_g
from public.device_diagnostics d
join public.plants p on p.id = d.plant_id
cross join lateral (
  select
    case when jsonb_typeof(d.details->'baseline_weight_g') = 'number'
      then (d.details->>'baseline_weight_g')::numeric
    end as baseline_g,
    case when jsonb_typeof(d.details->'increase_g') = 'number'
      then (d.details->>'increase_g')::numeric
    end as increase_g
) detection
left join lateral (
  select m.measured_at
  from public.weight_measurements m
  where m.plant_id = p.id
    and m.device_id = d.device_id
    and m.source = 'device'
    and m.is_stable
    and m.measured_at >= d.occurred_at - interval '30 minutes'
    and m.measured_at < d.occurred_at
    and abs(m.weight_g - detection.baseline_g) <= 3
    and not exists (
      select 1 from public.device_diagnostics reset
      where reset.device_id = d.device_id
        and reset.event_type in (
          'arduino_boot', 'arduino_restart_detected', 'collection_gap_power_or_restart',
          'gateway_run_stopped', 'serial_disconnected'
        )
        and reset.occurred_at > m.measured_at
        and reset.occurred_at <= d.occurred_at
    )
    and not exists (
      select 1 from public.care_events changed
      where changed.plant_id = p.id
        and (changed.device_id is null or changed.device_id = d.device_id)
        and changed.event_type in ('setup_changed', 'calibration')
        and changed.occurred_at > m.measured_at
        and changed.occurred_at <= d.occurred_at
    )
  order by m.measured_at desc, m.id desc
  limit 1
) previous on true
where d.event_type = 'watering_suspected';

revoke all on public.plant_watering_records from public, anon, authenticated;
grant select on public.plant_watering_records to authenticated;
