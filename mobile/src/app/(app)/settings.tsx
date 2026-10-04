import { useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAuth } from '@/context/auth';
import { useConversation } from '@/context/conversation';
import { usePlantProfile } from '@/context/plant-profile';

export default function SettingsScreen() {
  const { session, signOut } = useAuth();
  const { resetConversation } = useConversation();
  const { resetProfile } = usePlantProfile();
  const [busy, setBusy] = useState(false);
  const userName = session?.user.email?.split('@')[0] ?? '사용자';

  function confirmReset() {
    Alert.alert('로컬 데이터 초기화', '저장된 대화와 페르소나 설정을 기본값으로 되돌릴까요?', [
      { text: '취소', style: 'cancel' },
      {
        text: '초기화',
        style: 'destructive',
        onPress: () => {
          setBusy(true);
          void Promise.all([resetConversation(), resetProfile()]).finally(() => setBusy(false));
        },
      },
    ]);
  }

  async function logout() {
    setBusy(true);
    try {
      await signOut();
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView edges={['top']} style={styles.page}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.eyebrow}>SETTINGS</Text>
        <Text style={styles.title}>설정 관리</Text>
        <Text style={styles.description}>계정과 이 기기에 저장된 데이터를 관리합니다.</Text>

        <View style={styles.profileCard}>
          <View style={styles.avatar}><Text style={styles.avatarText}>🌱</Text></View>
          <View style={styles.profileText}>
            <Text style={styles.profileName}>{userName}</Text>
            <Text style={styles.profileEmail}>{session?.user.email}</Text>
          </View>
          <View style={styles.badge}><Text style={styles.badgeText}>로그인됨</Text></View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>데이터</Text>
          <View style={styles.row}>
            <View style={styles.rowText}>
              <Text style={styles.rowTitle}>대화 및 페르소나</Text>
              <Text style={styles.rowDescription}>현재 단계에서는 이 기기에만 저장됩니다.</Text>
            </View>
            <Text style={styles.localBadge}>로컬</Text>
          </View>
          <View style={styles.divider} />
          <Pressable disabled={busy} onPress={confirmReset} style={({ pressed }) => [styles.textButton, pressed && styles.pressed]}>
            <Text style={styles.dangerText}>로컬 데이터 초기화</Text>
          </Pressable>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>앱 정보</Text>
          <View style={styles.row}>
            <Text style={styles.rowTitle}>PlanTalk</Text>
            <Text style={styles.version}>MVP 0.1</Text>
          </View>
          <Text style={styles.info}>Supabase 로그인과 Gemini 채팅을 사용하는 개발 버전입니다.</Text>
        </View>

        <Pressable disabled={busy} onPress={() => void logout()} style={({ pressed }) => [styles.logoutButton, pressed && styles.pressed]}>
          <Text style={styles.logoutText}>{busy ? '처리 중…' : '로그아웃'}</Text>
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
  profileCard: { flexDirection: 'row', alignItems: 'center', padding: 18, marginTop: 22, borderRadius: 20, backgroundColor: '#245d42' },
  avatar: { width: 50, height: 50, alignItems: 'center', justifyContent: 'center', borderRadius: 16, backgroundColor: '#e2f2e6' },
  avatarText: { fontSize: 27 },
  profileText: { flex: 1, marginLeft: 13 },
  profileName: { color: '#fff', fontSize: 18, fontWeight: '800' },
  profileEmail: { color: '#d3e7d9', fontSize: 12, marginTop: 4 },
  badge: { paddingHorizontal: 9, paddingVertical: 6, borderRadius: 9, backgroundColor: '#3e7759' },
  badgeText: { color: '#e7f4ea', fontSize: 10, fontWeight: '700' },
  section: { padding: 18, marginTop: 16, borderRadius: 20, backgroundColor: '#fff' },
  sectionTitle: { color: '#183d2a', fontSize: 16, fontWeight: '800', marginBottom: 14 },
  row: { flexDirection: 'row', alignItems: 'center' },
  rowText: { flex: 1, paddingRight: 12 },
  rowTitle: { color: '#294334', fontSize: 14, fontWeight: '700' },
  rowDescription: { color: '#77857d', fontSize: 12, lineHeight: 18, marginTop: 4 },
  localBadge: { color: '#247a52', fontSize: 11, fontWeight: '700', paddingHorizontal: 9, paddingVertical: 5, borderRadius: 8, backgroundColor: '#e7f3ea' },
  divider: { height: 1, backgroundColor: '#e7ece8', marginVertical: 15 },
  textButton: { alignSelf: 'flex-start', paddingVertical: 4 },
  dangerText: { color: '#b42318', fontSize: 13, fontWeight: '700' },
  version: { marginLeft: 'auto', color: '#7b8980', fontSize: 12 },
  info: { color: '#77857d', fontSize: 12, lineHeight: 18, marginTop: 11 },
  logoutButton: { minHeight: 52, alignItems: 'center', justifyContent: 'center', marginTop: 18, borderRadius: 14, borderWidth: 1, borderColor: '#cbd8ce', backgroundColor: '#fff' },
  logoutText: { color: '#315941', fontSize: 15, fontWeight: '800' },
  pressed: { opacity: 0.72 },
});
