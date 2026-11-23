import { useCallback, useEffect, useRef, useState } from 'react';

import type { WaterHistoryItem } from '@/lib/water-history-transform';

export type WaterHistoryLoader = (plantId: string) => Promise<WaterHistoryItem[]>;

export function useWaterHistory(
  plantId: string | null | undefined,
  loadHistory: WaterHistoryLoader,
) {
  const [items, setItems] = useState<WaterHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const refresh = useCallback(async () => {
    const currentRequest = ++requestId.current;
    if (!plantId) {
      setItems([]);
      setError(null);
      setIsLoading(false);
      return true;
    }

    setIsLoading(true);
    setError(null);
    try {
      const nextItems = await loadHistory(plantId);
      if (currentRequest === requestId.current) setItems(nextItems);
      return true;
    } catch (reason) {
      if (currentRequest === requestId.current) {
        setError(reason instanceof Error ? reason.message : '측정 이력을 불러오지 못했습니다.');
      }
      return false;
    } finally {
      if (currentRequest === requestId.current) setIsLoading(false);
    }
  }, [loadHistory, plantId]);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      void refresh();
    }, 0);
    return () => {
      clearTimeout(timeoutId);
      requestId.current += 1;
    };
  }, [refresh]);

  return { items, isLoading, error, refresh };
}
