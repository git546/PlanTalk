import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { AppIcon } from '@/components/app-icon';
import { parseLocalizedNumber } from '@/lib/number-input';
import { recordManualCareEvent } from '@/lib/water-history';
import { colors, layout, radius, spacing } from '@/theme/tokens';

type Props = {
  userId: string;
  plantId: string;
};

type Notice = { text: string; isError?: boolean };

function parseWateringVolume(text: string): number | null {
  // care_events.volume_ml is numeric(12, 3).
  if (!/^\d{0,9}(?:[.,]\d{1,3})?$/.test(text.trim())) return null;
  const volume = parseLocalizedNumber(text);
  return volume !== null && volume > 0 ? volume : null;
}

export function HomeWateringCard({ userId, plantId }: Props) {
  const storageKey = `@plantalk/home-watering-volume/${userId}/${plantId}`;
  const [draft, setDraft] = useState('');
  const [savedVolume, setSavedVolume] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRecording, setIsRecording] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const busy = useRef(false);
  const volume = parseWateringVolume(draft);
  const invalidVolume = draft.trim() !== '' && volume === null;
  const isDisabled = isLoading || isRecording;
  const canRecord = !isDisabled && volume !== null;
  const isSavedVolume = volume !== null && volume === savedVolume;
  const displayedNotice = invalidVolume
    ? { text: '0보다 큰 급수량을 소수 셋째 자리까지 입력해 주세요.', isError: true }
    : notice;

  useEffect(() => {
    let active = true;
    async function loadVolume() {
      try {
        const stored = await AsyncStorage.getItem(storageKey);
        if (!active || stored === null) return;
        const storedVolume = parseWateringVolume(stored);
        if (storedVolume === null) return;
        setSavedVolume(storedVolume);
        setDraft(String(storedVolume));
      } catch {
        if (active) setNotice({ text: '저장된 급수량을 불러오지 못했어요.', isError: true });
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void loadVolume();
    return () => { active = false; };
  }, [storageKey]);

  async function recordWatering() {
    if (!canRecord || volume === null || busy.current) return;

    busy.current = true;
    setIsRecording(true);
    setNotice(null);
    try {
      await recordManualCareEvent(plantId, 'watering', volume);
      const success = `${volume} mL 급수를 기록했어요.`;
      setDraft(String(volume));
      if (!isSavedVolume) {
        try {
          await AsyncStorage.setItem(storageKey, String(volume));
          setSavedVolume(volume);
        } catch {
          setNotice({ text: `${success} 다음에 사용할 급수량은 저장하지 못했어요.` });
          return;
        }
      }
      setNotice({ text: success });
    } catch {
      setNotice({ text: '급수 기록을 저장하지 못했어요. 다시 시도해 주세요.', isError: true });
    } finally {
      busy.current = false;
      setIsRecording(false);
    }
  }

  return (
    <View style={styles.card}>
      <View style={styles.labelRow}>
        <Text accessibilityRole="header" style={styles.label}>1회 급수량</Text>
        {(isLoading || isSavedVolume) && (
          <Text accessibilityLiveRegion="polite" style={styles.saved}>
            {isLoading ? '불러오는 중' : '저장됨'}
          </Text>
        )}
      </View>
      <View style={styles.inputGroup}>
        <TextInput
          accessibilityLabel="1회 급수량 (mL)"
          editable={!isDisabled}
          inputMode="decimal"
          onChangeText={(text) => {
            setDraft(text);
            setNotice(null);
          }}
          placeholder="급수량 입력"
          placeholderTextColor={colors.textSecondary}
          style={styles.input}
          value={draft}
        />
        <Text accessible={false} style={styles.unit}>mL</Text>
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ disabled: !canRecord, busy: isRecording }}
        disabled={!canRecord}
        onPress={recordWatering}
        style={({ pressed }) => [
          styles.recordButton,
          !canRecord && styles.disabled,
          pressed && styles.pressed,
        ]}
      >
        <AppIcon color={colors.surface} name="water-outline" size={19} />
        <Text style={styles.recordText}>{isRecording ? '기록 중' : '물 주기'}</Text>
      </Pressable>
      <Text
        accessibilityLiveRegion="polite"
        style={[styles.status, displayedNotice?.isError && styles.error]}
      >
        {displayedNotice?.text ?? (
          isLoading ? '' : '물을 준 양을 입력하고 눌러 주세요.'
        )}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginTop: spacing.md, padding: spacing.lg, gap: spacing.sm,
    borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  labelRow: {
    flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center',
    justifyContent: 'space-between', gap: spacing.xs,
  },
  label: { color: colors.text, fontSize: 16, fontWeight: '800' },
  saved: { color: colors.brand, fontSize: 12, fontWeight: '700' },
  inputGroup: {
    flexDirection: 'row', alignItems: 'center',
    borderRadius: radius.md, borderWidth: 1, borderColor: colors.borderStrong,
    backgroundColor: colors.surfaceMuted,
  },
  input: {
    flex: 1, minWidth: 0, minHeight: layout.minimumTapTarget,
    paddingHorizontal: spacing.md, color: colors.text, fontSize: 16,
  },
  unit: { marginRight: spacing.md, color: colors.textSecondary, fontSize: 13 },
  recordButton: {
    minHeight: 48, paddingHorizontal: spacing.md, flexDirection: 'row', gap: spacing.sm,
    alignItems: 'center', justifyContent: 'center', borderRadius: radius.md,
    backgroundColor: colors.brand,
  },
  recordText: { color: colors.surface, fontSize: 15, fontWeight: '800' },
  status: { color: colors.textSecondary, fontSize: 12, lineHeight: 18 },
  error: { color: colors.danger },
  disabled: { opacity: 0.55 },
  pressed: { opacity: 0.72 },
});
