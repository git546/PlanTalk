import {
  loadWaterHistory,
  recordManualCareEvent,
  recordManualWeight,
} from '@/lib/water-history';

const mockFrom = jest.fn();

jest.mock('@/lib/supabase', () => ({
  supabase: {
    from: (table: string) => mockFrom(table),
  },
}));

type QueryResult = {
  data: unknown[] | null;
  error: { message: string } | null;
};

function selectQuery(result: QueryResult) {
  const query = {
    select: jest.fn(),
    eq: jest.fn(),
    in: jest.fn(),
    order: jest.fn(),
    limit: jest.fn().mockResolvedValue(result),
  };
  query.select.mockReturnValue(query);
  query.eq.mockReturnValue(query);
  query.in.mockReturnValue(query);
  query.order.mockReturnValue(query);
  return query;
}

describe('water history Supabase adapter', () => {
  beforeEach(() => {
    mockFrom.mockReset();
  });

  test('조회 결과가 비어 있으면 빈 이력을 반환한다', async () => {
    mockFrom
      .mockReturnValueOnce(selectQuery({ data: [], error: null }))
      .mockReturnValueOnce(selectQuery({ data: [], error: null }));

    await expect(loadWaterHistory('plant-1')).resolves.toEqual([]);
    expect(mockFrom).toHaveBeenNthCalledWith(1, 'weight_measurements');
    expect(mockFrom).toHaveBeenNthCalledWith(2, 'care_events');
  });

  test('무게 조회 실패를 사용자용 오류로 변환한다', async () => {
    mockFrom
      .mockReturnValueOnce(selectQuery({ data: null, error: { message: 'RLS denied' } }))
      .mockReturnValueOnce(selectQuery({ data: [], error: null }));

    await expect(loadWaterHistory('plant-1')).rejects.toThrow(
      '무게 이력을 불러오지 못했습니다. (RLS denied)',
    );
  });

  test('급수 이력 조회 실패를 사용자용 오류로 변환한다', async () => {
    mockFrom
      .mockReturnValueOnce(selectQuery({ data: [], error: null }))
      .mockReturnValueOnce(selectQuery({ data: null, error: { message: 'network down' } }));

    await expect(loadWaterHistory('plant-1')).rejects.toThrow(
      '급수·배수 이력을 불러오지 못했습니다. (network down)',
    );
  });

  test('수동 무게 저장 요청에 식물과 측정 출처를 포함한다', async () => {
    const insert = jest.fn().mockResolvedValue({ error: null });
    mockFrom.mockReturnValue({ insert });

    await recordManualWeight('plant-1', 1480.5);

    expect(mockFrom).toHaveBeenCalledWith('weight_measurements');
    expect(insert).toHaveBeenCalledWith(expect.objectContaining({
      plant_id: 'plant-1',
      source: 'manual',
      weight_g: 1480.5,
      is_stable: true,
    }));
  });

  test('Supabase 저장 실패를 성공으로 처리하지 않는다', async () => {
    const insert = jest.fn().mockResolvedValue({ error: { message: 'insert blocked' } });
    mockFrom.mockReturnValue({ insert });

    await expect(recordManualWeight('plant-1', 1480.5)).rejects.toThrow(
      '무게를 기록하지 못했습니다. (insert blocked)',
    );
  });

  test('급수 기록에 이벤트 종류와 입력량을 보낸다', async () => {
    const insert = jest.fn().mockResolvedValue({ error: null });
    mockFrom.mockReturnValue({ insert });

    await recordManualCareEvent('plant-1', 'watering', 25);

    expect(mockFrom).toHaveBeenCalledWith('care_events');
    expect(insert).toHaveBeenCalledWith(expect.objectContaining({
      plant_id: 'plant-1',
      event_type: 'watering',
      source: 'manual',
      volume_ml: 25,
    }));
  });
});
