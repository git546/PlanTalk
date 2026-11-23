import { mergeWaterHistory } from '@/lib/water-history-transform';

describe('mergeWaterHistory', () => {
  const weights = [
    { id: 1, weight_g: '1480.5', measured_at: '2026-11-20T10:00:00.000Z' },
    { id: 2, weight_g: 1500, measured_at: '2026-11-20T08:00:00.000Z' },
  ];
  const events = [
    {
      id: 'watering-1',
      event_type: 'watering' as const,
      volume_ml: '25',
      occurred_at: '2026-11-20T09:00:00.000Z',
    },
  ];

  test('무게와 돌봄 기록을 최신순으로 합치고 단위를 보존한다', () => {
    expect(mergeWaterHistory(weights, events)).toEqual([
      {
        id: 'weight-1',
        kind: 'weight',
        value: 1480.5,
        unit: 'g',
        occurredAt: '2026-11-20T10:00:00.000Z',
      },
      {
        id: 'event-watering-1',
        kind: 'watering',
        value: 25,
        unit: 'mL',
        occurredAt: '2026-11-20T09:00:00.000Z',
      },
      {
        id: 'weight-2',
        kind: 'weight',
        value: 1500,
        unit: 'g',
        occurredAt: '2026-11-20T08:00:00.000Z',
      },
    ]);
  });

  test('요청한 개수만 반환한다', () => {
    expect(mergeWaterHistory(weights, events, 2)).toHaveLength(2);
  });

  test('동일한 Supabase 행이 중복으로 전달돼도 한 번만 표시한다', () => {
    expect(mergeWaterHistory([weights[0], weights[0]], [events[0], events[0]])).toHaveLength(2);
  });
});
