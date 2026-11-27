import AsyncStorage from '@react-native-async-storage/async-storage';
import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';

import { HomeWateringCard } from '@/components/home-watering-card';

const mockInsert = jest.fn();

jest.mock('@/lib/supabase', () => ({
  supabase: {
    from: (table: string) => ({
      insert: (row: unknown) => mockInsert(table, row),
    }),
  },
}));

jest.mock('@/components/app-icon', () => ({ AppIcon: () => null }));

jest.mock('@react-native-async-storage/async-storage', () => {
  const stored = new Map<string, string>();
  return {
    getItem: async (key: string) => stored.get(key) ?? null,
    setItem: async (key: string, value: string) => { stored.set(key, value); },
    clear: async () => { stored.clear(); },
  };
});

describe('home watering', () => {
  beforeEach(async () => {
    await AsyncStorage.clear();
    mockInsert.mockReset().mockResolvedValue({ error: null });
  });

  test('records the entered amount in one press and remembers it for that plant', async () => {
    const card = await render(<HomeWateringCard userId="user-1" plantId="plant-1" />);
    const amount = screen.getByLabelText('1회 급수량 (mL)');
    await waitFor(() => expect(amount).toBeEnabled());

    expect(amount).toHaveDisplayValue('');
    expect(screen.getByRole('button', { name: '물 주기' })).toBeDisabled();
    expect(mockInsert).not.toHaveBeenCalled();
    await fireEvent.changeText(amount, '25,5');
    expect(screen.queryByRole('button', { name: '1회 급수량 저장' })).toBeNull();
    expect(mockInsert).not.toHaveBeenCalled();
    const startedAt = Date.now();
    await fireEvent.press(screen.getByRole('button', { name: '물 주기' }));
    await screen.findByText('25.5 mL 급수를 기록했어요.');
    expect(mockInsert).toHaveBeenCalledTimes(1);
    expect(mockInsert).toHaveBeenCalledWith('care_events', expect.objectContaining({
      plant_id: 'plant-1',
      event_type: 'watering',
      source: 'manual',
      volume_ml: 25.5,
    }));
    const at = Date.parse(mockInsert.mock.calls[0][1].occurred_at);
    expect(at).toBeGreaterThanOrEqual(startedAt);
    expect(at).toBeLessThanOrEqual(Date.now());

    await card.rerender(<HomeWateringCard key="plant-2" userId="user-1" plantId="plant-2" />);
    expect(screen.getByLabelText('1회 급수량 (mL)')).toHaveDisplayValue('');
    expect(mockInsert).toHaveBeenCalledTimes(1);

    await card.rerender(<HomeWateringCard key="plant-1" userId="user-1" plantId="plant-1" />);
    await screen.findByText('저장됨');
    const restoredAmount = screen.getByLabelText('1회 급수량 (mL)');
    expect(restoredAmount).toHaveDisplayValue('25.5');

    await fireEvent.changeText(restoredAmount, '30');
    expect(screen.queryByText('저장됨')).toBeNull();
    await fireEvent.press(screen.getByRole('button', { name: '물 주기' }));
    await screen.findByText('30 mL 급수를 기록했어요.');
    expect(mockInsert).toHaveBeenLastCalledWith('care_events', expect.objectContaining({
      plant_id: 'plant-1',
      volume_ml: 30,
    }));
  }, 15000);

  test('rejects an invalid amount and lets the user retry a failed recording', async () => {
    await render(<HomeWateringCard userId="user-1" plantId="plant-1" />);
    const amount = screen.getByLabelText('1회 급수량 (mL)');
    await waitFor(() => expect(amount).toBeEnabled());
    await fireEvent.changeText(amount, '-25');
    await screen.findByText('0보다 큰 급수량을 소수 셋째 자리까지 입력해 주세요.');
    expect(screen.getByRole('button', { name: '물 주기' })).toBeDisabled();

    await fireEvent.changeText(amount, '25');
    mockInsert.mockResolvedValueOnce({ error: { message: 'offline' } });
    await fireEvent.press(screen.getByRole('button', { name: '물 주기' }));
    await screen.findByText('급수 기록을 저장하지 못했어요. 다시 시도해 주세요.');
    await fireEvent.press(screen.getByRole('button', { name: '물 주기' }));
    await screen.findByText('25 mL 급수를 기록했어요.');
  });
});
