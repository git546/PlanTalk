import { useEffect, useState } from 'react';
import { router, type Href } from 'expo-router';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { usePlantCatalog } from '@/context/plant-catalog';
import {
  fetchWaterBalance,
  type WaterBalanceRequest,
  type WaterBalanceResponse,
} from '@/lib/api';
import {
  loadWaterHistory,
  recordManualCareEvent,
  recordManualWeight,
  type WaterHistoryItem,
} from '@/lib/water-history';

type InputKey =
  | 'periodDays'
  | 'currentWeight'
  | 'waterAdded'
  | 'drainage';

type InputValues = Record<InputKey, string>;

const EMPTY_VALUES: InputValues = {
  periodDays: '',
  currentWeight: '',
  waterAdded: '',
  drainage: '',
};

const STATUS_TEXT: Record<WaterBalanceResponse['status'], string> = {
  hydrated: '목표 수분 범위 이상이에요',
  monitor: '조금 더 지켜봐도 괜찮아요',
  water_soon: '곧 물주기 기준에 도달해요',
  water_now: '현재 물주기 기준에 도달했어요',
};

const CONFIDENCE_TEXT: Record<WaterBalanceResponse['confidence'], string> = {
  low: '낮음',
  medium: '보통',
  high: '높음',
};

function NumberInput({
  label,
  unit,
  value,
  hint,
  onChangeText,
}: {
  label: string;
  unit: string;
  value: string;
  hint?: string;
  onChangeText: (value: string) => void;
}) {
  return (
    <View style={styles.inputGroup}>
      <View style={styles.inputHeading}>
        <Text style={styles.inputLabel}>{label}</Text>
        <Text style={styles.inputUnit}>{unit}</Text>
      </View>
      <TextInput
        accessibilityLabel={`${label} ${unit}`}
        keyboardType="decimal-pad"
        onChangeText={onChangeText}
        placeholder="0"
        placeholderTextColor="#9aa69e"
        style={styles.input}
        value={value}
      />
      {hint ? <Text style={styles.inputHint}>{hint}</Text> : null}
    </View>
  );
}

function parseNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value.trim().replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : null;
}

function ResultItem({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.resultItem}>
      <Text style={styles.resultLabel}>{label}</Text>
      <Text style={styles.resultValue}>{value}</Text>
    </View>
  );
}

const HISTORY_LABEL: Record<WaterHistoryItem['kind'], string> = {
  weight: '무게',
  watering: '급수',
  drainage: '배수',
};

function formatRecordedAt(value: string): string {
  return new Date(value).toLocaleString('ko-KR', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function WaterCalculatorScreen() {
  const { plants, selectedPlant, selectedPlantId, selectPlant } = usePlantCatalog();
  const [values, setValues] = useState<InputValues>(EMPTY_VALUES);
  const [result, setResult] = useState<WaterBalanceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<WaterHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordWeight, setRecordWeight] = useState('');
  const [careVolume, setCareVolume] = useState('');
  const [careType, setCareType] = useState<'watering' | 'drainage'>('watering');
  const [recordMessage, setRecordMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadHistory() {
      if (!selectedPlantId) {
        setHistory([]);
        return;
      }
      setHistoryLoading(true);
      setRecordMessage(null);
      try {
        const items = await loadWaterHistory(selectedPlantId);
        if (active) setHistory(items);
      } catch (reason) {
        if (active) {
          setRecordMessage(
            reason instanceof Error ? reason.message : '측정 이력을 불러오지 못했습니다.',
          );
        }
      } finally {
        if (active) setHistoryLoading(false);
      }
    }
    void loadHistory();
    return () => { active = false; };
  }, [selectedPlantId]);

  async function choosePlant(plantId: string) {
    setValues(EMPTY_VALUES);
    setResult(null);
    setError(null);
    setRecordWeight('');
    setCareVolume('');
    setRecordMessage(null);
    await selectPlant(plantId);
  }

  async function refreshHistory() {
    if (!selectedPlantId) return;
    setHistory(await loadWaterHistory(selectedPlantId));
  }

  async function saveWeightRecord() {
    if (!selectedPlantId) {
      setRecordMessage('먼저 식물을 선택해 주세요.');
      return;
    }
    const weight = parseNumber(recordWeight || values.currentWeight);
    if (weight === null || weight <= 0) {
      setRecordMessage('기록할 현재 무게를 0보다 큰 숫자로 입력해 주세요.');
      return;
    }
    setRecording(true);
    setRecordMessage(null);
    try {
      await recordManualWeight(selectedPlantId, weight);
      await refreshHistory();
      setRecordWeight('');
      setRecordMessage('현재 무게를 Supabase에 기록했습니다.');
    } catch (reason) {
      setRecordMessage(reason instanceof Error ? reason.message : '무게를 기록하지 못했습니다.');
    } finally {
      setRecording(false);
    }
  }

  async function saveCareRecord() {
    if (!selectedPlantId) {
      setRecordMessage('먼저 식물을 선택해 주세요.');
      return;
    }
    const volume = parseNumber(careVolume);
    if (volume === null || volume <= 0) {
      setRecordMessage('이번 1회 급수·배수량을 0보다 큰 숫자로 입력해 주세요.');
      return;
    }
    setRecording(true);
    setRecordMessage(null);
    try {
      await recordManualCareEvent(selectedPlantId, careType, volume);
      await refreshHistory();
      setCareVolume('');
      setRecordMessage(`${careType === 'watering' ? '급수' : '배수'} 기록을 저장했습니다.`);
    } catch (reason) {
      setRecordMessage(
        reason instanceof Error ? reason.message : '급수·배수 기록을 저장하지 못했습니다.',
      );
    } finally {
      setRecording(false);
    }
  }

  function updateValue(key: InputKey, value: string) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function buildRequest(): WaterBalanceRequest | null {
    if (
      !selectedPlant
      || selectedPlant.setupWeightG === null
      || selectedPlant.targetWetWeightG === null
      || selectedPlant.wateringTriggerWeightG === null
    ) return null;
    const required = {
      period_days: parseNumber(values.periodDays),
      end_pot_weight_g: parseNumber(values.currentWeight),
      water_added_ml: parseNumber(values.waterAdded),
      drainage_ml: parseNumber(values.drainage),
    };
    if (Object.values(required).some((value) => value === null)) return null;

    return {
      period_days: required.period_days!,
      start_pot_weight_g: selectedPlant.setupWeightG,
      end_pot_weight_g: required.end_pot_weight_g!,
      water_added_ml: required.water_added_ml!,
      drainage_ml: required.drainage_ml!,
      target_wet_weight_g: selectedPlant.targetWetWeightG,
      watering_trigger_weight_g: selectedPlant.wateringTriggerWeightG,
      ...(selectedPlant.maxSingleWateringMl === null
        ? {}
        : { max_single_watering_ml: selectedPlant.maxSingleWateringMl }),
    };
  }

  async function calculate() {
    if (!selectedPlant) {
      setError('먼저 식물 관리에서 식물을 등록해 주세요.');
      return;
    }
    if (
      selectedPlant.setupWeightG === null
      || selectedPlant.targetWetWeightG === null
      || selectedPlant.wateringTriggerWeightG === null
    ) {
      setError('선택한 식물의 화분 기준 무게를 먼저 저장해 주세요.');
      return;
    }
    const request = buildRequest();
    if (!request) {
      setError('필수 입력값을 모두 숫자로 입력해 주세요.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setResult(await fetchWaterBalance(request));
    } catch (reason) {
      setResult(null);
      setError(reason instanceof Error ? reason.message : '계산 중 문제가 발생했어요.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView edges={['top']} style={styles.page}>
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.eyebrow}>WATER BALANCE</Text>
        <Text style={styles.title}>수분량 계산기</Text>
        <Text style={styles.description}>
          화분 세팅 직후부터 누적된 급수량·배수량과 현재 무게로 수분 손실을 추정합니다.
        </Text>

        {plants.length > 0 ? (
          <View style={styles.plantSelector}>
            <Text style={styles.selectorLabel}>계산할 식물</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.plantChips}>
              {plants.map((plant) => (
                <Pressable
                  key={plant.id}
                  onPress={() => void choosePlant(plant.id)}
                  style={[styles.plantChip, plant.id === selectedPlantId && styles.plantChipSelected]}
                >
                  <Text style={[styles.plantChipText, plant.id === selectedPlantId && styles.plantChipTextSelected]}>{plant.name}</Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        ) : null}

        <View style={styles.notice}>
          <View style={styles.noticeHeader}>
            <Text style={styles.noticeTitle}>{selectedPlant ? `${selectedPlant.name} 기준값` : '식물 등록 필요'}</Text>
            <Pressable onPress={() => router.push('/plants' as Href)}>
              <Text style={styles.noticeLink}>{selectedPlant ? '설정 변경' : '식물 추가'}</Text>
            </Pressable>
          </View>
          {selectedPlant ? (
            <Text style={styles.noticeText}>
              세팅 {selectedPlant.setupWeightG ?? '미설정'}g · 목표 {selectedPlant.targetWetWeightG ?? '미설정'}g · 물주기 기준 {selectedPlant.wateringTriggerWeightG ?? '미설정'}g
            </Text>
          ) : (
            <Text style={styles.noticeText}>식물을 추가하고 화분 세팅 기준 무게를 먼저 저장해 주세요.</Text>
          )}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>세팅 이후 누적 측정값</Text>
          <NumberInput
            label="세팅 후 경과 기간"
            unit="일"
            value={values.periodDays}
            onChangeText={(value) => updateValue('periodDays', value)}
          />
          <NumberInput
            label="현재 화분 무게"
            unit="g"
            value={values.currentWeight}
            hint="처음 세팅할 때와 같은 받침·센서 상태로 측정"
            onChangeText={(value) => updateValue('currentWeight', value)}
          />
          <NumberInput
            label="누적 급수량"
            unit="mL"
            value={values.waterAdded}
            hint="화분 세팅 이후 지금까지 준 물의 합계"
            onChangeText={(value) => updateValue('waterAdded', value)}
          />
          <NumberInput
            label="누적 배수량"
            unit="mL"
            value={values.drainage}
            hint="화분 세팅 이후 받침이나 배수통으로 나온 물의 합계"
            onChangeText={(value) => updateValue('drainage', value)}
          />
        </View>

        <View style={styles.actionRow}>
          <Pressable
            onPress={() => { setValues(EMPTY_VALUES); setResult(null); setError(null); }}
            style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}
          >
            <Text style={styles.secondaryButtonText}>초기화</Text>
          </Pressable>
          <Pressable
            disabled={loading}
            onPress={() => void calculate()}
            style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed, loading && styles.disabled]}
          >
            {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryButtonText}>계산하기</Text>}
          </Pressable>
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        {result ? (
          <View style={styles.resultCard}>
            <View style={styles.resultHeader}>
              <View style={styles.resultHeaderText}>
                <Text style={styles.resultEyebrow}>계산 결과</Text>
                <Text style={styles.resultStatus}>{STATUS_TEXT[result.status]}</Text>
              </View>
              <View style={styles.confidenceBadge}>
                <Text style={styles.confidenceText}>신뢰도 {CONFIDENCE_TEXT[result.confidence]}</Text>
              </View>
            </View>

            <View style={styles.resultGrid}>
              <ResultItem label="기간 중 수분 손실" value={`${result.estimated_water_loss_ml} mL`} />
              <ResultItem label="하루 평균 손실" value={`${result.average_daily_loss_ml} mL`} />
              <ResultItem label="목표까지 부족량" value={`${result.refill_to_target_ml} mL`} />
              <ResultItem label="지금 권장 급수량" value={`${result.recommended_water_now_ml} mL`} />
              <ResultItem
                label="예상 물주기까지"
                value={result.estimated_days_until_watering === null ? '계산 불가' : `${result.estimated_days_until_watering}일`}
              />
              <ResultItem
                label="배수 비율"
                value={result.drainage_ratio_percent === null ? '급수 기록 없음' : `${result.drainage_ratio_percent}%`}
              />
            </View>

            {result.warnings.length > 0 ? (
              <View style={styles.warningBox}>
                <Text style={styles.warningTitle}>확인할 점</Text>
                {result.warnings.map((warning) => <Text key={warning} style={styles.warningText}>• {warning}</Text>)}
              </View>
            ) : null}
            <Text style={styles.assumption}>{result.assumption} 수분 손실에는 식물의 증산과 흙 표면 증발이 모두 포함됩니다.</Text>
          </View>
        ) : null}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>측정·돌봄 기록</Text>
          <Text style={styles.historyDescription}>
            계산기의 누적값과 별개로, 실제로 방금 측정하거나 준 1회분만 저장합니다.
          </Text>

          <Text style={styles.recordLabel}>현재 안정 무게</Text>
          <View style={styles.recordRow}>
            <TextInput
              accessibilityLabel="기록할 현재 무게"
              keyboardType="decimal-pad"
              onChangeText={setRecordWeight}
              placeholder={values.currentWeight || '0'}
              placeholderTextColor="#9aa69e"
              style={[styles.input, styles.recordInput]}
              value={recordWeight}
            />
            <Text style={styles.recordUnit}>g</Text>
            <Pressable
              disabled={recording || !selectedPlantId}
              onPress={() => void saveWeightRecord()}
              style={({ pressed }) => [
                styles.recordButton,
                pressed && styles.pressed,
                (recording || !selectedPlantId) && styles.disabled,
              ]}
            >
              <Text style={styles.recordButtonText}>무게 기록</Text>
            </Pressable>
          </View>

          <Text style={styles.recordLabel}>이번 1회 급수·배수량</Text>
          <View style={styles.typeRow}>
            {(['watering', 'drainage'] as const).map((type) => (
              <Pressable
                key={type}
                onPress={() => setCareType(type)}
                style={[styles.typeButton, careType === type && styles.typeButtonSelected]}
              >
                <Text style={[
                  styles.typeButtonText,
                  careType === type && styles.typeButtonTextSelected,
                ]}>
                  {type === 'watering' ? '급수' : '배수'}
                </Text>
              </Pressable>
            ))}
          </View>
          <View style={styles.recordRow}>
            <TextInput
              accessibilityLabel="이번 1회 급수 또는 배수량"
              keyboardType="decimal-pad"
              onChangeText={setCareVolume}
              placeholder="0"
              placeholderTextColor="#9aa69e"
              style={[styles.input, styles.recordInput]}
              value={careVolume}
            />
            <Text style={styles.recordUnit}>mL</Text>
            <Pressable
              disabled={recording || !selectedPlantId}
              onPress={() => void saveCareRecord()}
              style={({ pressed }) => [
                styles.recordButton,
                pressed && styles.pressed,
                (recording || !selectedPlantId) && styles.disabled,
              ]}
            >
              <Text style={styles.recordButtonText}>{careType === 'watering' ? '급수 기록' : '배수 기록'}</Text>
            </Pressable>
          </View>

          {recordMessage ? <Text style={styles.recordMessage}>{recordMessage}</Text> : null}

          <View style={styles.historyDivider} />
          <Text style={styles.historyTitle}>최근 기록</Text>
          {historyLoading ? (
            <ActivityIndicator color="#247a52" style={styles.historyLoading} />
          ) : history.length === 0 ? (
            <Text style={styles.historyEmpty}>아직 저장된 기록이 없습니다.</Text>
          ) : (
            <View style={styles.historyList}>
              {history.map((item) => (
                <View key={item.id} style={styles.historyItem}>
                  <View style={styles.historyBadge}>
                    <Text style={styles.historyBadgeText}>{HISTORY_LABEL[item.kind]}</Text>
                  </View>
                  <Text style={styles.historyValue}>{item.value} {item.unit}</Text>
                  <Text style={styles.historyDate}>{formatRecordedAt(item.occurredAt)}</Text>
                </View>
              ))}
            </View>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#e8eee9' },
  content: {
    width: '100%', maxWidth: 480, minHeight: '100%', alignSelf: 'center',
    paddingHorizontal: 16, paddingTop: 18, paddingBottom: 48, backgroundColor: '#f5f8f4',
    borderLeftWidth: 1, borderRightWidth: 1, borderColor: '#dde7df',
  },
  eyebrow: { color: '#247a52', fontSize: 11, fontWeight: '800', letterSpacing: 1.2 },
  title: { color: '#183d2a', fontSize: 26, lineHeight: 35, fontWeight: '800', marginTop: 5 },
  description: { color: '#66766d', fontSize: 13, lineHeight: 20, marginTop: 6 },
  plantSelector: { marginTop: 18 },
  selectorLabel: { color: '#405347', fontSize: 12, fontWeight: '800', marginBottom: 8 },
  plantChips: { gap: 8, paddingRight: 12 },
  plantChip: { paddingHorizontal: 13, paddingVertical: 9, borderWidth: 1, borderColor: '#cbd8ce', borderRadius: 12, backgroundColor: '#fff' },
  plantChipSelected: { borderColor: '#247a52', backgroundColor: '#247a52' },
  plantChipText: { color: '#52645a', fontSize: 12, fontWeight: '700' },
  plantChipTextSelected: { color: '#fff' },
  notice: { padding: 15, marginTop: 18, borderRadius: 16, backgroundColor: '#e2f2e6' },
  noticeHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  noticeTitle: { color: '#245d42', fontSize: 13, fontWeight: '800' },
  noticeLink: { color: '#247a52', fontSize: 11, fontWeight: '800' },
  noticeText: { color: '#4b6756', fontSize: 12, lineHeight: 18, marginTop: 5 },
  section: { padding: 17, marginTop: 15, borderRadius: 20, backgroundColor: '#fff' },
  sectionTitle: { color: '#183d2a', fontSize: 16, fontWeight: '800', marginBottom: 4 },
  inputGroup: { marginTop: 14 },
  inputHeading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 7 },
  inputLabel: { color: '#334d3d', fontSize: 13, fontWeight: '700' },
  inputUnit: { color: '#7b8980', fontSize: 11, fontWeight: '600' },
  input: { minHeight: 48, paddingHorizontal: 14, borderWidth: 1, borderColor: '#d5e0d7', borderRadius: 12, color: '#183d2a', fontSize: 16, backgroundColor: '#fafcf9' },
  inputHint: { color: '#849087', fontSize: 11, lineHeight: 16, marginTop: 5 },
  actionRow: { flexDirection: 'row', gap: 10, marginTop: 18 },
  secondaryButton: { flex: 1, minHeight: 51, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#b9cbbd', borderRadius: 14, backgroundColor: '#fff' },
  secondaryButtonText: { color: '#315941', fontSize: 14, fontWeight: '800' },
  primaryButton: { flex: 2, minHeight: 51, alignItems: 'center', justifyContent: 'center', borderRadius: 14, backgroundColor: '#247a52' },
  primaryButtonText: { color: '#fff', fontSize: 14, fontWeight: '800' },
  disabled: { opacity: 0.58 },
  pressed: { opacity: 0.74 },
  error: { color: '#b42318', fontSize: 12, lineHeight: 18, marginTop: 12 },
  resultCard: { padding: 18, marginTop: 18, borderRadius: 22, backgroundColor: '#245d42' },
  resultHeader: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
  resultHeaderText: { flex: 1, paddingRight: 10 },
  resultEyebrow: { color: '#b9d7c4', fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  resultStatus: { color: '#fff', fontSize: 19, lineHeight: 27, fontWeight: '800', marginTop: 5 },
  confidenceBadge: { paddingHorizontal: 9, paddingVertical: 6, borderRadius: 9, backgroundColor: '#3e7759' },
  confidenceText: { color: '#e7f4ea', fontSize: 10, fontWeight: '700' },
  resultGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 9, marginTop: 17 },
  resultItem: { width: '48%', minHeight: 77, padding: 12, borderRadius: 13, backgroundColor: '#356d50' },
  resultLabel: { color: '#c8dfd0', fontSize: 10, lineHeight: 15 },
  resultValue: { color: '#fff', fontSize: 17, fontWeight: '800', marginTop: 6 },
  warningBox: { padding: 13, marginTop: 14, borderRadius: 13, backgroundColor: '#fff1d9' },
  warningTitle: { color: '#704d18', fontSize: 12, fontWeight: '800', marginBottom: 4 },
  warningText: { color: '#735927', fontSize: 11, lineHeight: 17, marginTop: 3 },
  assumption: { color: '#c8dfd0', fontSize: 10, lineHeight: 16, marginTop: 14 },
  historyDescription: { color: '#77857d', fontSize: 11, lineHeight: 17, marginTop: 4 },
  recordLabel: { color: '#405347', fontSize: 12, fontWeight: '800', marginTop: 16, marginBottom: 7 },
  recordRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  recordInput: { flex: 1, minWidth: 0 },
  recordUnit: { width: 24, color: '#77857d', fontSize: 11, fontWeight: '700' },
  recordButton: { minWidth: 82, minHeight: 48, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 10, borderRadius: 12, backgroundColor: '#247a52' },
  recordButtonText: { color: '#fff', fontSize: 11, fontWeight: '800' },
  typeRow: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  typeButton: { paddingHorizontal: 14, paddingVertical: 8, borderWidth: 1, borderColor: '#cbd8ce', borderRadius: 10, backgroundColor: '#fff' },
  typeButtonSelected: { borderColor: '#247a52', backgroundColor: '#e5f2e8' },
  typeButtonText: { color: '#64756b', fontSize: 11, fontWeight: '700' },
  typeButtonTextSelected: { color: '#247a52' },
  recordMessage: { color: '#247a52', fontSize: 11, lineHeight: 17, marginTop: 10 },
  historyDivider: { height: 1, backgroundColor: '#e6ece7', marginVertical: 17 },
  historyTitle: { color: '#294334', fontSize: 13, fontWeight: '800' },
  historyLoading: { marginTop: 18 },
  historyEmpty: { color: '#849087', fontSize: 11, marginTop: 12 },
  historyList: { gap: 8, marginTop: 11 },
  historyItem: { minHeight: 42, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, borderRadius: 11, backgroundColor: '#f4f8f4' },
  historyBadge: { minWidth: 38, paddingHorizontal: 7, paddingVertical: 4, borderRadius: 7, backgroundColor: '#e0efe4' },
  historyBadgeText: { color: '#247a52', fontSize: 10, fontWeight: '800', textAlign: 'center' },
  historyValue: { color: '#294334', fontSize: 12, fontWeight: '800', marginLeft: 9 },
  historyDate: { color: '#7c8981', fontSize: 10, marginLeft: 'auto' },
});
