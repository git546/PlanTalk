import { act, renderHook, waitFor } from '@testing-library/react-native';

import { useWaterHistory, type WaterHistoryLoader } from '@/hooks/use-water-history';

const SAMPLE_ITEM = {
  id: 'weight-1',
  kind: 'weight' as const,
  value: 1480,
  unit: 'g' as const,
  occurredAt: '2026-11-20T10:00:00.000Z',
};

describe('useWaterHistory', () => {
  test('선택한 식물의 기록을 불러온다', async () => {
    const loader = jest.fn<ReturnType<WaterHistoryLoader>, Parameters<WaterHistoryLoader>>()
      .mockResolvedValue([SAMPLE_ITEM]);
    const { result } = await renderHook(() => useWaterHistory('plant-1', loader));

    await waitFor(() => expect(result.current.items).toEqual([SAMPLE_ITEM]));

    expect(loader).toHaveBeenCalledWith('plant-1');
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  test('식물이 없으면 원격 조회 없이 빈 기록을 유지한다', async () => {
    const loader = jest.fn<ReturnType<WaterHistoryLoader>, Parameters<WaterHistoryLoader>>();
    const { result } = await renderHook(() => useWaterHistory(null, loader));

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(loader).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.items).toEqual([]);
  });

  test('조회 실패를 사용자에게 표시할 오류로 보관하고 다시 시도할 수 있다', async () => {
    const loader = jest.fn<ReturnType<WaterHistoryLoader>, Parameters<WaterHistoryLoader>>()
      .mockRejectedValueOnce(new Error('센서 기록 조회 실패'))
      .mockResolvedValueOnce([SAMPLE_ITEM]);
    const { result } = await renderHook(() => useWaterHistory('plant-1', loader));

    await waitFor(() => expect(result.current.error).toBe('센서 기록 조회 실패'));

    let refreshed = false;
    await act(async () => {
      refreshed = await result.current.refresh();
    });

    expect(refreshed).toBe(true);
    expect(result.current.error).toBeNull();
    expect(result.current.items).toEqual([SAMPLE_ITEM]);
    expect(loader).toHaveBeenCalledTimes(2);
  });

  test('새로고침이 실패해도 이미 표시한 기록을 지우지 않는다', async () => {
    const loader = jest.fn<ReturnType<WaterHistoryLoader>, Parameters<WaterHistoryLoader>>()
      .mockResolvedValueOnce([SAMPLE_ITEM])
      .mockRejectedValueOnce(new Error('Supabase 연결 실패'));
    const { result } = await renderHook(() => useWaterHistory('plant-1', loader));
    await waitFor(() => expect(result.current.items).toEqual([SAMPLE_ITEM]));

    let refreshed = true;
    await act(async () => {
      refreshed = await result.current.refresh();
    });

    expect(refreshed).toBe(false);
    expect(result.current.items).toEqual([SAMPLE_ITEM]);
    expect(result.current.error).toBe('Supabase 연결 실패');
  });
});
