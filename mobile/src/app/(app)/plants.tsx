import { useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { type ManagedPlant, usePlantCatalog } from '@/context/plant-catalog';

type CalibrationDraft = {
  setupWeight: string;
  targetWeight: string;
  triggerWeight: string;
  maxWatering: string;
};

const EMPTY_CALIBRATION: CalibrationDraft = {
  setupWeight: '', targetWeight: '', triggerWeight: '', maxWatering: '',
};

function formatValue(value: number | null) {
  return value === null ? '' : String(value);
}

function calibrationFromPlant(plant: ManagedPlant | null): CalibrationDraft {
  if (!plant) return EMPTY_CALIBRATION;
  return {
    setupWeight: formatValue(plant.setupWeightG),
    targetWeight: formatValue(plant.targetWetWeightG),
    triggerWeight: formatValue(plant.wateringTriggerWeightG),
    maxWatering: formatValue(plant.maxSingleWateringMl),
  };
}

function parseRequired(value: string) {
  const parsed = Number(value.trim().replace(',', '.'));
  return value.trim() && Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function WeightInput({
  label, value, unit = 'g', hint, onChangeText,
}: {
  label: string;
  value: string;
  unit?: string;
  hint?: string;
  onChangeText: (value: string) => void;
}) {
  return (
    <View style={styles.field}>
      <View style={styles.fieldHeading}>
        <Text style={styles.fieldLabel}>{label}</Text><Text style={styles.unit}>{unit}</Text>
      </View>
      <TextInput
        keyboardType="decimal-pad"
        onChangeText={onChangeText}
        placeholder="0"
        placeholderTextColor="#98a49c"
        style={styles.input}
        value={value}
      />
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  );
}

export default function PlantsScreen() {
  const {
    plants, selectedPlant, selectedPlantId, syncError,
    selectPlant, addPlant, updatePlant, deletePlant,
  } = usePlantCatalog();
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState('');
  const [newSpecies, setNewSpecies] = useState('');
  const [draftOverride, setDraft] = useState<CalibrationDraft | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const draft = draftOverride ?? calibrationFromPlant(selectedPlant);

  function updateDraft(key: keyof CalibrationDraft, value: string) {
    setDraft((current) => ({ ...(current ?? calibrationFromPlant(selectedPlant)), [key]: value }));
    setMessage(null);
  }

  async function choosePlant(plantId: string) {
    setDraft(null);
    setMessage(null);
    await selectPlant(plantId);
  }

  async function createPlant() {
    if (!newName.trim()) {
      setMessage('식물 이름을 입력해 주세요.');
      return;
    }
    setBusy(true);
    try {
      await addPlant(newName, newSpecies);
      setDraft(null);
      setNewName('');
      setNewSpecies('');
      setShowAdd(false);
      setMessage('식물을 추가했습니다. 이제 기준 무게를 설정해 주세요.');
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : '식물을 추가하지 못했습니다.');
    } finally {
      setBusy(false);
    }
  }

  async function saveCalibration() {
    if (!selectedPlant) return;
    const setupWeight = parseRequired(draft.setupWeight);
    const targetWeight = parseRequired(draft.targetWeight);
    const triggerWeight = parseRequired(draft.triggerWeight);
    const maxWatering = draft.maxWatering.trim() ? parseRequired(draft.maxWatering) : null;
    if (setupWeight === null || targetWeight === null || triggerWeight === null) {
      setMessage('세 가지 기준 무게를 모두 0보다 큰 숫자로 입력해 주세요.');
      return;
    }
    if (triggerWeight >= targetWeight) {
      setMessage('물주기 시작 기준은 충분히 젖은 목표 무게보다 작아야 합니다.');
      return;
    }
    if (draft.maxWatering.trim() && maxWatering === null) {
      setMessage('1회 최대 급수량을 0보다 큰 숫자로 입력해 주세요.');
      return;
    }

    setBusy(true);
    try {
      await updatePlant({
        ...selectedPlant,
        setupWeightG: setupWeight,
        targetWetWeightG: targetWeight,
        wateringTriggerWeightG: triggerWeight,
        maxSingleWateringMl: maxWatering,
        calibrationUpdatedAt: new Date().toISOString(),
      });
      setDraft(null);
      setMessage('무게 기준을 Supabase에 저장했습니다.');
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : '무게 기준을 저장하지 못했습니다.');
    } finally {
      setBusy(false);
    }
  }

  function confirmDelete(plant: ManagedPlant) {
    Alert.alert('식물 삭제', `${plant.name}의 무게 설정을 삭제할까요?`, [
      { text: '취소', style: 'cancel' },
      {
        text: '삭제',
        style: 'destructive',
        onPress: () => {
          setDraft(null);
          setBusy(true);
          void deletePlant(plant.id)
            .catch((reason) => {
              setMessage(reason instanceof Error ? reason.message : '식물을 삭제하지 못했습니다.');
            })
            .finally(() => setBusy(false));
        },
      },
    ]);
  }

  return (
    <SafeAreaView edges={['top']} style={styles.page}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.headerRow}>
          <View style={styles.headerText}>
            <Text style={styles.eyebrow}>MY PLANTS</Text>
            <Text style={styles.title}>식물 관리</Text>
            <Text style={styles.description}>화분별 무게 기준을 저장하고 계산할 식물을 선택합니다.</Text>
          </View>
          <Pressable onPress={() => setShowAdd((current) => !current)} style={styles.addButton}>
            <Text style={styles.addButtonText}>{showAdd ? '닫기' : '+ 추가'}</Text>
          </Pressable>
        </View>

        {syncError ? <Text style={styles.syncError}>{syncError}</Text> : null}

        {showAdd ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>새 식물</Text>
            <Text style={styles.fieldLabel}>식물 이름</Text>
            <TextInput value={newName} onChangeText={setNewName} style={styles.input} placeholder="예: 초록이" />
            <Text style={styles.fieldLabel}>식물 종류</Text>
            <TextInput value={newSpecies} onChangeText={setNewSpecies} style={styles.input} placeholder="예: 몬스테라" />
            <Pressable disabled={busy} onPress={() => void createPlant()} style={styles.primaryButton}>
              <Text style={styles.primaryButtonText}>{busy ? '저장 중…' : '목록에 추가'}</Text>
            </Pressable>
          </View>
        ) : null}

        {plants.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyEmoji}>🪴</Text>
            <Text style={styles.emptyTitle}>등록된 식물이 없습니다</Text>
            <Text style={styles.emptyText}>식물을 추가한 뒤 화분 세팅 무게를 기록해 주세요.</Text>
          </View>
        ) : (
          <View style={styles.plantList}>
            {plants.map((plant) => {
              const selected = plant.id === selectedPlantId;
              const calibrated = plant.setupWeightG !== null
                && plant.targetWetWeightG !== null
                && plant.wateringTriggerWeightG !== null;
              return (
                <Pressable
                  key={plant.id}
                  onPress={() => void choosePlant(plant.id)}
                  style={[styles.plantCard, selected && styles.plantCardSelected]}
                >
                  <View style={styles.plantIcon}><Text style={styles.plantEmoji}>🌿</Text></View>
                  <View style={styles.plantText}>
                    <Text style={styles.plantName}>{plant.name}</Text>
                    <Text style={styles.plantMeta}>{plant.species} · {calibrated ? '보정값 저장됨' : '보정 필요'}</Text>
                  </View>
                  {selected ? <Text style={styles.selectedBadge}>선택됨</Text> : null}
                  <Pressable hitSlop={8} onPress={() => confirmDelete(plant)} style={styles.deleteButton}>
                    <Text style={styles.deleteText}>삭제</Text>
                  </Pressable>
                </Pressable>
              );
            })}
          </View>
        )}

        {selectedPlant ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>{selectedPlant.name} 무게 설정</Text>
            <Text style={styles.sectionDescription}>화분이나 흙을 바꾸면 이 기준을 다시 측정해 주세요.</Text>
            <WeightInput
              label="화분 세팅 기준 무게"
              value={draft.setupWeight}
              hint="식물·흙·화분·센서 세팅을 마친 직후의 무게"
              onChangeText={(value) => updateDraft('setupWeight', value)}
            />
            <WeightInput
              label="충분히 젖은 목표 무게"
              value={draft.targetWeight}
              hint="물을 준 뒤 배수가 멈춘 시점의 무게"
              onChangeText={(value) => updateDraft('targetWeight', value)}
            />
            <WeightInput
              label="물주기 시작 기준 무게"
              value={draft.triggerWeight}
              hint="관찰을 통해 물이 필요하다고 판단한 무게"
              onChangeText={(value) => updateDraft('triggerWeight', value)}
            />
            <WeightInput
              label="한 번에 줄 최대량"
              value={draft.maxWatering}
              unit="mL · 선택"
              onChangeText={(value) => updateDraft('maxWatering', value)}
            />
            {message ? <Text style={styles.message}>{message}</Text> : null}
            <Pressable disabled={busy} onPress={() => void saveCalibration()} style={styles.primaryButton}>
              <Text style={styles.primaryButtonText}>{busy ? '저장 중…' : '무게 기준 저장'}</Text>
            </Pressable>
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#e8eee9' },
  content: { width: '100%', maxWidth: 480, minHeight: '100%', alignSelf: 'center', paddingHorizontal: 16, paddingTop: 18, paddingBottom: 42, backgroundColor: '#f5f8f4', borderLeftWidth: 1, borderRightWidth: 1, borderColor: '#dde7df' },
  headerRow: { flexDirection: 'row', alignItems: 'flex-start' },
  headerText: { flex: 1, paddingRight: 10 },
  eyebrow: { color: '#247a52', fontSize: 11, fontWeight: '800', letterSpacing: 1.2 },
  title: { color: '#183d2a', fontSize: 26, fontWeight: '800', marginTop: 5 },
  description: { color: '#6d7c73', fontSize: 13, lineHeight: 19, marginTop: 5 },
  addButton: { paddingHorizontal: 13, paddingVertical: 9, borderRadius: 11, backgroundColor: '#247a52' },
  addButtonText: { color: '#fff', fontSize: 12, fontWeight: '800' },
  section: { padding: 18, marginTop: 16, borderRadius: 20, backgroundColor: '#fff' },
  sectionTitle: { color: '#183d2a', fontSize: 17, fontWeight: '800', marginBottom: 5 },
  sectionDescription: { color: '#77857d', fontSize: 12, lineHeight: 18, marginBottom: 7 },
  field: { marginTop: 13 },
  fieldHeading: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 7 },
  fieldLabel: { color: '#405347', fontSize: 13, fontWeight: '700', marginTop: 10, marginBottom: 7 },
  unit: { color: '#7b8980', fontSize: 11, fontWeight: '600' },
  input: { minHeight: 48, borderWidth: 1, borderColor: '#cddacf', borderRadius: 12, paddingHorizontal: 13, color: '#183d2a', backgroundColor: '#fbfdfb', fontSize: 15 },
  hint: { color: '#849087', fontSize: 11, lineHeight: 16, marginTop: 5 },
  primaryButton: { minHeight: 50, alignItems: 'center', justifyContent: 'center', marginTop: 15, borderRadius: 13, backgroundColor: '#247a52' },
  primaryButtonText: { color: '#fff', fontSize: 14, fontWeight: '800' },
  plantList: { gap: 10, marginTop: 20 },
  plantCard: { minHeight: 76, flexDirection: 'row', alignItems: 'center', padding: 13, borderWidth: 1, borderColor: '#dce5de', borderRadius: 17, backgroundColor: '#fff' },
  plantCardSelected: { borderColor: '#247a52', backgroundColor: '#eaf5ed' },
  plantIcon: { width: 45, height: 45, alignItems: 'center', justifyContent: 'center', borderRadius: 13, backgroundColor: '#dff0e3' },
  plantEmoji: { fontSize: 23 },
  plantText: { flex: 1, marginLeft: 11 },
  plantName: { color: '#183d2a', fontSize: 16, fontWeight: '800' },
  plantMeta: { color: '#758279', fontSize: 11, marginTop: 4 },
  selectedBadge: { color: '#247a52', fontSize: 10, fontWeight: '800', marginRight: 8 },
  deleteButton: { paddingVertical: 7, paddingLeft: 5 },
  deleteText: { color: '#a5483d', fontSize: 11, fontWeight: '700' },
  emptyCard: { alignItems: 'center', padding: 28, marginTop: 20, borderRadius: 20, backgroundColor: '#fff' },
  emptyEmoji: { fontSize: 38 },
  emptyTitle: { color: '#284533', fontSize: 16, fontWeight: '800', marginTop: 9 },
  emptyText: { color: '#7a887f', fontSize: 12, marginTop: 5 },
  message: { color: '#247a52', fontSize: 12, lineHeight: 18, marginTop: 12 },
  syncError: { color: '#b42318', fontSize: 12, lineHeight: 18, marginTop: 12 },
});
