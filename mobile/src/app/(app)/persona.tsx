import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { type PlantProfile, usePlantProfile } from '@/context/plant-profile';

const TONE_OPTIONS: { value: PlantProfile['tonePreset']; label: string; description: string }[] = [
  { value: 'warm', label: '다정한 친구', description: '따뜻하고 편안한 반말' },
  { value: 'bright', label: '활발한 친구', description: '밝고 장난스러운 반말' },
  { value: 'calm', label: '차분한 조언자', description: '신중하고 세심한 존댓말' },
];

type LevelPickerProps = {
  label: string;
  value: number;
  onChange: (value: number) => void;
};

function LevelPicker({ label, value, onChange }: LevelPickerProps) {
  return (
    <View style={styles.levelRow}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.levels}>
        {[1, 2, 3, 4, 5].map((level) => (
          <Pressable
            key={level}
            accessibilityRole="button"
            onPress={() => onChange(level)}
            style={[styles.level, value === level && styles.levelSelected]}
          >
            <Text style={[styles.levelText, value === level && styles.levelTextSelected]}>{level}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

export default function PersonaScreen() {
  const { profile, saveProfile } = usePlantProfile();
  const [draftOverride, setDraft] = useState<PlantProfile | null>(null);
  const [saved, setSaved] = useState(false);
  const draft = draftOverride ?? profile;

  function update<K extends keyof PlantProfile>(key: K, value: PlantProfile[K]) {
    setDraft((previous) => ({ ...(previous ?? profile), [key]: value }));
    setSaved(false);
  }

  async function save() {
    const next = {
      ...draft,
      name: draft.name.trim() || '초록이',
      species: draft.species.trim() || '식물',
      callingUser: draft.callingUser.trim() || '친구',
      customDescription: draft.customDescription.trim(),
      speechExample: draft.speechExample.trim(),
    };
    await saveProfile(next);
    setDraft(next);
    setSaved(true);
  }

  return (
    <SafeAreaView edges={['top']} style={styles.page}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.eyebrow}>PERSONA</Text>
        <Text style={styles.title}>식물의 성격 만들기</Text>
        <Text style={styles.description}>저장한 성격은 다음 대화부터 바로 적용됩니다.</Text>

        <View style={styles.preview}>
          <Text style={styles.previewEmoji}>🪴</Text>
          <View style={styles.previewText}>
            <Text style={styles.previewName}>{draft.name || '이름 없는 식물'}</Text>
            <Text style={styles.previewLine}>“{draft.callingUser || '친구'}, 오늘은 어떤 하루였어?”</Text>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>기본 정보</Text>
          <Text style={styles.fieldLabel}>식물 이름</Text>
          <TextInput value={draft.name} onChangeText={(value) => update('name', value)} maxLength={50} style={styles.input} placeholder="예: 초록이" />
          <Text style={styles.fieldLabel}>식물 종류</Text>
          <TextInput value={draft.species} onChangeText={(value) => update('species', value)} maxLength={80} style={styles.input} placeholder="예: 몬스테라" />
          <Text style={styles.fieldLabel}>나를 부르는 호칭</Text>
          <TextInput value={draft.callingUser} onChangeText={(value) => update('callingUser', value)} maxLength={20} style={styles.input} placeholder="예: 친구, 주인님" />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>기본 성격</Text>
          <View style={styles.toneList}>
            {TONE_OPTIONS.map((option) => (
              <Pressable
                key={option.value}
                onPress={() => update('tonePreset', option.value)}
                style={[styles.toneCard, draft.tonePreset === option.value && styles.toneCardSelected]}
              >
                <View style={[styles.radio, draft.tonePreset === option.value && styles.radioSelected]} />
                <View style={styles.toneText}>
                  <Text style={styles.toneTitle}>{option.label}</Text>
                  <Text style={styles.toneDescription}>{option.description}</Text>
                </View>
              </Pressable>
            ))}
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>성격 세부 조절</Text>
          <LevelPicker label="활발함" value={draft.energy} onChange={(value) => update('energy', value)} />
          <LevelPicker label="애정 표현" value={draft.affection} onChange={(value) => update('affection', value)} />
          <LevelPicker label="유머" value={draft.humor} onChange={(value) => update('humor', value)} />
          <Text style={styles.fieldLabel}>답변 길이</Text>
          <View style={styles.segmented}>
            {(['짧게', '보통', '길게'] as const).map((length) => (
              <Pressable key={length} onPress={() => update('talkLength', length)} style={[styles.segment, draft.talkLength === length && styles.segmentSelected]}>
                <Text style={[styles.segmentText, draft.talkLength === length && styles.segmentTextSelected]}>{length}</Text>
              </Pressable>
            ))}
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>직접 설정</Text>
          <Text style={styles.sectionHint}>프리셋으로 표현하기 어려운 성격과 말버릇을 자유롭게 적어 주세요.</Text>
          <Text style={styles.fieldLabel}>직접 성격 설명</Text>
          <TextInput
            value={draft.customDescription}
            onChangeText={(value) => update('customDescription', value)}
            maxLength={300}
            multiline
            numberOfLines={5}
            textAlignVertical="top"
            style={[styles.input, styles.longInput]}
            placeholder="예: 낯을 조금 가리지만 친해지면 말이 많아지고, 힘들어할 때는 조용히 위로한다."
            placeholderTextColor="#8a968e"
          />
          <Text style={styles.counter}>{draft.customDescription.length}/300</Text>

          <Text style={styles.fieldLabel}>말투 예시</Text>
          <TextInput
            value={draft.speechExample}
            onChangeText={(value) => update('speechExample', value)}
            maxLength={200}
            multiline
            numberOfLines={3}
            textAlignVertical="top"
            style={[styles.input, styles.exampleInput]}
            placeholder="예: 친구야, 오늘은 햇빛도 좋으니까 우리 둘 다 조금 기운 내보자."
            placeholderTextColor="#8a968e"
          />
          <Text style={styles.counter}>{draft.speechExample.length}/200</Text>
        </View>

        <Pressable onPress={() => void save()} style={({ pressed }) => [styles.saveButton, pressed && styles.pressed]}>
          <Text style={styles.saveButtonText}>{saved ? '저장됐어요 ✓' : '페르소나 저장'}</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#e8eee9' },
  content: {
    width: '100%', maxWidth: 480, minHeight: '100%', alignSelf: 'center',
    paddingHorizontal: 16, paddingTop: 18, paddingBottom: 40, backgroundColor: '#f5f8f4',
    borderLeftWidth: 1, borderRightWidth: 1, borderColor: '#dde7df',
  },
  eyebrow: { color: '#247a52', fontSize: 11, fontWeight: '800', letterSpacing: 1.2 },
  title: { color: '#183d2a', fontSize: 26, lineHeight: 35, fontWeight: '800', marginTop: 5 },
  description: { color: '#6d7c73', fontSize: 13, marginTop: 5 },
  preview: { flexDirection: 'row', alignItems: 'center', padding: 18, marginTop: 22, borderRadius: 20, backgroundColor: '#245d42' },
  previewEmoji: { fontSize: 39, marginRight: 14 },
  previewText: { flex: 1 },
  previewName: { color: '#fff', fontSize: 19, fontWeight: '800' },
  previewLine: { color: '#d7e8dc', fontSize: 13, lineHeight: 19, marginTop: 5 },
  section: { padding: 18, marginTop: 16, borderRadius: 20, backgroundColor: '#fff' },
  sectionTitle: { color: '#183d2a', fontSize: 17, fontWeight: '800', marginBottom: 15 },
  sectionHint: { color: '#77857d', fontSize: 12, lineHeight: 18, marginTop: -7, marginBottom: 7 },
  fieldLabel: { color: '#405347', fontSize: 13, fontWeight: '700', marginBottom: 7, marginTop: 8 },
  input: { minHeight: 48, borderWidth: 1, borderColor: '#cddacf', borderRadius: 12, paddingHorizontal: 13, color: '#183d2a', backgroundColor: '#fbfdfb', fontSize: 15, marginBottom: 7 },
  longInput: { minHeight: 116, paddingTop: 12, lineHeight: 21 },
  exampleInput: { minHeight: 84, paddingTop: 12, lineHeight: 21 },
  counter: { color: '#89958e', fontSize: 11, textAlign: 'right', marginTop: -2, marginBottom: 5 },
  toneList: { gap: 9 },
  toneCard: { minHeight: 67, flexDirection: 'row', alignItems: 'center', padding: 13, borderWidth: 1, borderColor: '#dae4dc', borderRadius: 14 },
  toneCardSelected: { borderColor: '#247a52', backgroundColor: '#edf6ef' },
  radio: { width: 18, height: 18, borderRadius: 9, borderWidth: 2, borderColor: '#a5b5aa', marginRight: 12 },
  radioSelected: { borderWidth: 5, borderColor: '#247a52', backgroundColor: '#fff' },
  toneText: { flex: 1 },
  toneTitle: { color: '#233d2d', fontSize: 14, fontWeight: '700' },
  toneDescription: { color: '#77857c', fontSize: 12, marginTop: 3 },
  levelRow: { marginBottom: 13 },
  levels: { flexDirection: 'row', gap: 8 },
  level: { flex: 1, height: 38, alignItems: 'center', justifyContent: 'center', borderRadius: 10, borderWidth: 1, borderColor: '#ccd9ce', backgroundColor: '#fff' },
  levelSelected: { borderColor: '#247a52', backgroundColor: '#247a52' },
  levelText: { color: '#607068', fontSize: 13, fontWeight: '700' },
  levelTextSelected: { color: '#fff' },
  segmented: { flexDirection: 'row', gap: 8 },
  segment: { flex: 1, alignItems: 'center', paddingVertical: 11, borderRadius: 10, backgroundColor: '#edf1ee' },
  segmentSelected: { backgroundColor: '#dcefe1' },
  segmentText: { color: '#68776e', fontSize: 13, fontWeight: '700' },
  segmentTextSelected: { color: '#247a52' },
  saveButton: { minHeight: 54, alignItems: 'center', justifyContent: 'center', marginTop: 18, borderRadius: 15, backgroundColor: '#247a52' },
  saveButtonText: { color: '#fff', fontSize: 16, fontWeight: '800' },
  pressed: { opacity: 0.8 },
});
