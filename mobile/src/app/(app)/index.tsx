import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAuth } from '@/context/auth';
import { useConversation } from '@/context/conversation';
import { usePlantProfile } from '@/context/plant-profile';

type MenuCardProps = {
  eyebrow: string;
  title: string;
  description: string;
  color: string;
  onPress: () => void;
};

function MenuCard({ eyebrow, title, description, color, onPress }: MenuCardProps) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.menuCard, { backgroundColor: color }, pressed && styles.pressed]}
    >
      <Text style={styles.eyebrow}>{eyebrow}</Text>
      <Text style={styles.menuTitle}>{title}</Text>
      <Text numberOfLines={2} style={styles.menuDescription}>{description}</Text>
      <Text style={styles.arrow}>→</Text>
    </Pressable>
  );
}

export default function DashboardScreen() {
  const { session } = useAuth();
  const { profile } = usePlantProfile();
  const { messages, resetConversation } = useConversation();
  const userName = session?.user.email?.split('@')[0] ?? '사용자';
  const lastMessage = [...messages].reverse().find((message) => message.sender === 'plant');

  async function startNewConversation() {
    await resetConversation();
    router.push('/chat');
  }

  return (
    <SafeAreaView style={styles.page}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View>
            <Text style={styles.brand}>PlanTalk</Text>
            <Text style={styles.greeting}>{userName}님, 반가워요.</Text>
          </View>
          <View style={styles.avatar}><Text style={styles.avatarText}>🌿</Text></View>
        </View>

        <View style={styles.plantCard}>
          <View style={styles.plantVisual}><Text style={styles.plantEmoji}>🪴</Text></View>
          <View style={styles.plantInfo}>
            <Text style={styles.cardLabel}>현재 대화 상대</Text>
            <Text style={styles.plantName}>{profile.name}</Text>
            <Text style={styles.plantMeta}>{profile.species} · {profile.callingUser}라고 부르는 중</Text>
          </View>
          <Pressable onPress={() => router.push('/persona')} style={styles.editButton}>
            <Text style={styles.editButtonText}>편집</Text>
          </Pressable>
        </View>

        <View style={styles.sectionHeading}>
          <Text style={styles.sectionTitle}>무엇을 할까요?</Text>
          <Text style={styles.sectionDescription}>식물과의 대화와 성격을 한곳에서 관리해요.</Text>
        </View>

        <MenuCard
          eyebrow="CHAT"
          title="채팅 관리"
          description={lastMessage?.text ?? '아직 대화가 없어요. 먼저 인사해 보세요.'}
          color="#e2f2e6"
          onPress={() => router.push('/chat')}
        />
        <View style={styles.inlineActions}>
          <Pressable onPress={() => router.push('/chat')} style={styles.secondaryButton}>
            <Text style={styles.secondaryButtonText}>이어가기</Text>
          </Pressable>
          <Pressable onPress={() => void startNewConversation()} style={styles.primaryButton}>
            <Text style={styles.primaryButtonText}>새 대화</Text>
          </Pressable>
        </View>

        <View style={styles.cardGrid}>
          <MenuCard
            eyebrow="PERSONA"
            title="페르소나 관리"
            description="말투와 성격, 호칭을 바꿔요."
            color="#fff1d9"
            onPress={() => router.push('/persona')}
          />
          <MenuCard
            eyebrow="SETTINGS"
            title="설정 관리"
            description="계정과 저장 데이터를 확인해요."
            color="#e7edf9"
            onPress={() => router.push('/settings')}
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#e8eee9' },
  content: {
    width: '100%', maxWidth: 480, minHeight: '100%', alignSelf: 'center',
    paddingHorizontal: 16, paddingTop: 18, paddingBottom: 32, backgroundColor: '#f7faf7',
    borderLeftWidth: 1, borderRightWidth: 1, borderColor: '#dde7df',
  },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22 },
  brand: { color: '#247a52', fontSize: 14, fontWeight: '800', letterSpacing: 0.8 },
  greeting: { color: '#183d2a', fontSize: 22, lineHeight: 30, fontWeight: '800', marginTop: 3 },
  avatar: { width: 44, height: 44, borderRadius: 15, alignItems: 'center', justifyContent: 'center', backgroundColor: '#fff' },
  avatarText: { fontSize: 23 },
  plantCard: { flexDirection: 'row', alignItems: 'center', padding: 14, borderRadius: 19, backgroundColor: '#245d42' },
  plantVisual: { width: 54, height: 54, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: '#e5f3e8' },
  plantEmoji: { fontSize: 30 },
  plantInfo: { flex: 1, marginHorizontal: 11 },
  cardLabel: { color: '#b9d7c4', fontSize: 11, fontWeight: '700' },
  plantName: { color: '#fff', fontSize: 19, fontWeight: '800', marginTop: 3 },
  plantMeta: { color: '#d7e8dc', fontSize: 11, marginTop: 4 },
  editButton: { paddingHorizontal: 10, paddingVertical: 7, borderRadius: 9, backgroundColor: '#fff' },
  editButtonText: { color: '#245d42', fontSize: 12, fontWeight: '700' },
  sectionHeading: { marginTop: 28, marginBottom: 13 },
  sectionTitle: { color: '#183d2a', fontSize: 19, fontWeight: '800' },
  sectionDescription: { color: '#718078', fontSize: 13, marginTop: 5 },
  menuCard: { flex: 1, minHeight: 122, borderRadius: 18, padding: 17, overflow: 'hidden' },
  eyebrow: { color: '#52705d', fontSize: 10, fontWeight: '800', letterSpacing: 1.1 },
  menuTitle: { color: '#183d2a', fontSize: 19, fontWeight: '800', marginTop: 9 },
  menuDescription: { color: '#536359', fontSize: 13, lineHeight: 19, marginTop: 7, paddingRight: 22 },
  arrow: { color: '#247a52', fontSize: 25, position: 'absolute', right: 17, bottom: 14 },
  inlineActions: { flexDirection: 'row', gap: 9, marginTop: 10 },
  secondaryButton: { flex: 1, alignItems: 'center', paddingHorizontal: 18, paddingVertical: 11, borderRadius: 12, borderWidth: 1, borderColor: '#b8cabc', backgroundColor: '#fff' },
  secondaryButtonText: { color: '#346048', fontSize: 13, fontWeight: '700' },
  primaryButton: { flex: 1, alignItems: 'center', paddingHorizontal: 18, paddingVertical: 11, borderRadius: 12, backgroundColor: '#247a52' },
  primaryButtonText: { color: '#fff', fontSize: 13, fontWeight: '700' },
  cardGrid: { gap: 12, marginTop: 16 },
  pressed: { opacity: 0.76 },
});
