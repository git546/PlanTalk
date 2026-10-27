-- Anonymous, read-only activity probe for the scheduled Supabase keepalive job.
-- It touches at most one plants row but never returns application data.
create or replace function public.keepalive()
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  perform 1 from public.plants limit 1;
  return true;
end;
$$;

revoke all on function public.keepalive() from public;
grant execute on function public.keepalive() to anon, authenticated;
