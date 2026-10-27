import { supabase } from '@/lib/supabase';

export type WaterHistoryItem = {
  id: string;
  kind: 'weight' | 'watering' | 'drainage';
  value: number;
  unit: 'g' | 'mL';
  occurredAt: string;
};

type WeightRow = {
  id: number | string;
  weight_g: number | string;
  measured_at: string;
};

type CareEventRow = {
  id: number | string;
  event_type: 'watering' | 'drainage';
  volume_ml: number | string;
  occurred_at: string;
};

function fail(action: string, detail?: string): Error {
  return new Error(detail ? `${action} (${detail})` : action);
}

export async function loadWaterHistory(
  plantId: string,
  limit = 20,
): Promise<WaterHistoryItem[]> {
  const [measurements, events] = await Promise.all([
    supabase
      .from('weight_measurements')
      .select('id,weight_g,measured_at')
      .eq('plant_id', plantId)
      .order('measured_at', { ascending: false })
      .limit(limit),
    supabase
      .from('care_events')
      .select('id,event_type,volume_ml,occurred_at')
      .eq('plant_id', plantId)
      .in('event_type', ['watering', 'drainage'])
      .order('occurred_at', { ascending: false })
      .limit(limit),
  ]);
  if (measurements.error) {
    throw fail('무게 이력을 불러오지 못했습니다.', measurements.error.message);
  }
  if (events.error) {
    throw fail('급수·배수 이력을 불러오지 못했습니다.', events.error.message);
  }

  const weightItems = ((measurements.data ?? []) as WeightRow[]).map((row) => ({
    id: `weight-${row.id}`,
    kind: 'weight' as const,
    value: Number(row.weight_g),
    unit: 'g' as const,
    occurredAt: row.measured_at,
  }));
  const eventItems = ((events.data ?? []) as CareEventRow[]).map((row) => ({
    id: `event-${row.id}`,
    kind: row.event_type,
    value: Number(row.volume_ml),
    unit: 'mL' as const,
    occurredAt: row.occurred_at,
  }));
  return [...weightItems, ...eventItems]
    .sort((left, right) => right.occurredAt.localeCompare(left.occurredAt))
    .slice(0, limit);
}

export async function recordManualWeight(plantId: string, weightG: number): Promise<void> {
  const now = new Date().toISOString();
  const { error } = await supabase.from('weight_measurements').insert({
    plant_id: plantId,
    source: 'manual',
    weight_g: weightG,
    is_stable: true,
    measured_at: now,
    raw_payload: { entry: 'mobile' },
  });
  if (error) throw fail('무게를 기록하지 못했습니다.', error.message);
}

export async function recordManualCareEvent(
  plantId: string,
  eventType: 'watering' | 'drainage',
  volumeMl: number,
): Promise<void> {
  const { error } = await supabase.from('care_events').insert({
    plant_id: plantId,
    event_type: eventType,
    source: 'manual',
    volume_ml: volumeMl,
    occurred_at: new Date().toISOString(),
    raw_payload: { entry: 'mobile' },
  });
  if (error) throw fail('급수·배수 기록을 저장하지 못했습니다.', error.message);
}
