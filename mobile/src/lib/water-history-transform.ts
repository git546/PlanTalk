export type WaterHistoryItem = {
  id: string;
  kind: 'weight' | 'watering' | 'drainage';
  value: number;
  unit: 'g' | 'mL';
  occurredAt: string;
};

export type WeightHistoryRow = {
  id: number | string;
  weight_g: number | string;
  measured_at: string;
};

export type CareEventHistoryRow = {
  id: number | string;
  event_type: 'watering' | 'drainage';
  volume_ml: number | string;
  occurred_at: string;
};

export function mergeWaterHistory(
  weights: WeightHistoryRow[],
  events: CareEventHistoryRow[],
  limit = 20,
): WaterHistoryItem[] {
  const weightItems: WaterHistoryItem[] = weights.map((row) => ({
    id: `weight-${row.id}`,
    kind: 'weight',
    value: Number(row.weight_g),
    unit: 'g',
    occurredAt: row.measured_at,
  }));
  const eventItems: WaterHistoryItem[] = events.map((row) => ({
    id: `event-${row.id}`,
    kind: row.event_type,
    value: Number(row.volume_ml),
    unit: 'mL',
    occurredAt: row.occurred_at,
  }));

  const uniqueItems = new Map(
    [...weightItems, ...eventItems].map((item) => [item.id, item]),
  );
  return [...uniqueItems.values()]
    .sort((left, right) => right.occurredAt.localeCompare(left.occurredAt))
    .slice(0, Math.max(0, limit));
}
