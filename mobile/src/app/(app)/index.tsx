import { router, type Href } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AppIcon } from '@/components/app-icon';
import { HomeWateringCard } from '@/components/home-watering-card';
import { useAuth } from '@/context/auth';
import { useConversation } from '@/context/conversation';
import { usePlantCatalog } from '@/context/plant-catalog';
import { usePlantProfile } from '@/context/plant-profile';
import { colors, layout, radius, spacing } from '@/theme/tokens';

type ActionRowProps = {
  icon: 'leaf-outline' | 'color-palette-outline' | 'settings-outline';
  title: string;
  description: string;
  onPress: () => void;
};

function ActionRow({ icon, title, description, onPress }: ActionRowProps) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.actionRow, pressed && styles.pressed]}
    >
      <View style={styles.actionIcon}>
        <AppIcon color={colors.brand} name={icon} size={21} />
      </View>
      <View style={styles.actionText}>
        <Text style={styles.actionTitle}>{title}</Text>
        <Text numberOfLines={2} style={styles.actionDescription}>{description}</Text>
      </View>
      <AppIcon color={colors.textMuted} name="chevron-forward" size={20} />
    </Pressable>
  );
}

export default function DashboardScreen() {
  const { session } = useAuth();
  const { profile } = usePlantProfile();
  const { selectedPlant, isLoading: plantsLoading } = usePlantCatalog();
  const { messages } = useConversation();
  const userName = session?.user.email?.split('@')[0] ?? '사용자';
  const lastMessage = [...messages].reverse().find((message) => message.sender === 'plant');
  const plantName = selectedPlant?.name ?? profile.name;
  const plantSpecies = selectedPlant?.species ?? profile.species;
  const isCalibrated = !!selectedPlant
    && selectedPlant.setupWeightG !== null
    && selectedPlant.targetWetWeightG !== null
    && selectedPlant.wateringTriggerWeightG !== null;

  const status = plantsLoading
    ? { label: '확인 중', title: '식물 정보를 불러오고 있어요', description: '잠시만 기다려 주세요.' }
    : !selectedPlant
      ? { label: '시작하기', title: '첫 식물을 등록해 주세요', description: '식물을 등록하면 상태 기록과 대화를 시작할 수 있어요.' }
      : isCalibrated
        ? { label: '측정 준비됨', title: '오늘 상태를 기록해 볼까요?', description: '기준 무게가 저장되어 있어 수분 상태를 계산할 수 있어요.' }
        : { label: '설정 필요', title: '초기 무게 기준이 필요해요', description: '정확한 계산을 위해 화분의 기준 무게를 먼저 설정해 주세요.' };

  function openPrimaryAction() {
    if (!selectedPlant || !isCalibrated) router.push('/plants' as Href);
    else router.push('/water' as Href);
  }

  return (
    <SafeAreaView style={styles.page}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <View>
            <Text style={styles.brand}>PLANTALK</Text>
            <Text accessibilityRole="header" style={styles.greeting}>{userName}님, 안녕하세요.</Text>
          </View>
          <View style={styles.headerIcon}>
            <AppIcon color={colors.brand} name="leaf" size={24} />
          </View>
        </View>

        <View style={styles.statusCard}>
          <View style={styles.statusTopRow}>
            <View style={styles.plantIdentity}>
              <View style={styles.plantIcon}>
                <AppIcon color={colors.brandStrong} name="leaf" size={25} />
              </View>
              <View style={styles.plantText}>
                <Text style={styles.plantName}>{plantName}</Text>
                <Text style={styles.plantSpecies}>{plantSpecies}</Text>
              </View>
            </View>
            <View style={styles.statusBadge}>
              <Text style={styles.statusBadgeText}>{status.label}</Text>
            </View>
          </View>

          <View style={styles.statusCopy}>
            <Text style={styles.statusTitle}>{status.title}</Text>
            <Text style={styles.statusDescription}>{status.description}</Text>
          </View>

          <View style={styles.primaryActions}>
            <Pressable
              accessibilityRole="button"
              onPress={openPrimaryAction}
              style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
            >
              <AppIcon color={colors.surface} name={isCalibrated ? 'water-outline' : 'options-outline'} size={19} />
              <Text style={styles.primaryButtonText}>{isCalibrated ? '오늘 상태 기록' : '초기 설정하기'}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => router.push('/chat')}
              style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}
            >
              <AppIcon color={colors.brand} name="chatbubble-ellipses-outline" size={19} />
              <Text style={styles.secondaryButtonText}>대화하기</Text>
            </Pressable>
          </View>
        </View>

        {!plantsLoading && session && selectedPlant && (
          <HomeWateringCard
            key={`${session.user.id}/${selectedPlant.id}`}
            userId={session.user.id}
            plantId={selectedPlant.id}
          />
        )}

        <View style={styles.sectionHeading}>
          <Text accessibilityRole="header" style={styles.sectionTitle}>최근 대화</Text>
          <Pressable accessibilityRole="button" onPress={() => router.push('/chat')} hitSlop={8}>
            <Text style={styles.textLink}>전체 보기</Text>
          </Pressable>
        </View>
        <Pressable
          accessibilityRole="button"
          onPress={() => router.push('/chat')}
          style={({ pressed }) => [styles.messagePreview, pressed && styles.pressed]}
        >
          <View style={styles.messageIcon}>
            <AppIcon color={colors.brand} name="chatbubble-ellipses" size={20} />
          </View>
          <View style={styles.messageText}>
            <Text style={styles.messageName}>{plantName}</Text>
            <Text numberOfLines={2} style={styles.messageBody}>
              {lastMessage?.text ?? '아직 대화가 없어요. 먼저 인사해 보세요.'}
            </Text>
          </View>
          <AppIcon color={colors.textMuted} name="chevron-forward" size={20} />
        </Pressable>

        <Text accessibilityRole="header" style={styles.sectionTitleStandalone}>관리</Text>
        <View style={styles.actionList}>
          <ActionRow
            icon="leaf-outline"
            title="식물과 화분 설정"
            description="식물 등록, 기준 무게와 참고 정보를 관리합니다."
            onPress={() => router.push('/plants' as Href)}
          />
          <ActionRow
            icon="color-palette-outline"
            title="대화 성격 설정"
            description={`${plantName}의 말투와 호칭을 조절합니다.`}
            onPress={() => router.push('/persona')}
          />
          <ActionRow
            icon="settings-outline"
            title="앱 설정"
            description="계정과 저장 데이터를 확인합니다."
            onPress={() => router.push('/settings')}
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.canvas },
  content: {
    width: '100%', maxWidth: layout.maxContentWidth, minHeight: '100%', alignSelf: 'center',
    paddingHorizontal: layout.pagePadding, paddingTop: spacing.lg, paddingBottom: spacing.xxl,
    backgroundColor: colors.canvas,
  },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.xl },
  brand: { color: colors.brand, fontSize: 12, fontWeight: '800', letterSpacing: 1.2 },
  greeting: { color: colors.text, fontSize: 24, lineHeight: 32, fontWeight: '800', marginTop: spacing.xs },
  headerIcon: { width: 44, height: 44, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surfaceBrand },
  statusCard: { padding: spacing.lg, borderRadius: radius.lg, backgroundColor: colors.brandStrong },
  statusTopRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  plantIdentity: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  plantIcon: { width: 48, height: 48, alignItems: 'center', justifyContent: 'center', borderRadius: radius.md, backgroundColor: colors.brandSoft },
  plantText: { flex: 1, marginLeft: spacing.md },
  plantName: { color: colors.surface, fontSize: 18, fontWeight: '800' },
  plantSpecies: { color: '#CFE1D5', fontSize: 13, marginTop: 3 },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: '#2D6649' },
  statusBadgeText: { color: colors.surface, fontSize: 11, fontWeight: '800' },
  statusCopy: { marginTop: spacing.xl },
  statusTitle: { color: colors.surface, fontSize: 21, lineHeight: 29, fontWeight: '800' },
  statusDescription: { color: '#D3E4D9', fontSize: 14, lineHeight: 21, marginTop: spacing.xs },
  primaryActions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.lg },
  primaryButton: { flex: 1.25, minHeight: 48, flexDirection: 'row', gap: spacing.sm, alignItems: 'center', justifyContent: 'center', borderRadius: radius.md, backgroundColor: colors.brand },
  primaryButtonText: { color: colors.surface, fontSize: 14, fontWeight: '800' },
  secondaryButton: { flex: 1, minHeight: 48, flexDirection: 'row', gap: spacing.sm, alignItems: 'center', justifyContent: 'center', borderRadius: radius.md, backgroundColor: colors.surface },
  secondaryButtonText: { color: colors.brand, fontSize: 14, fontWeight: '800' },
  sectionHeading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: spacing.xl, marginBottom: spacing.md },
  sectionTitle: { color: colors.text, fontSize: 18, fontWeight: '800' },
  textLink: { color: colors.brand, fontSize: 13, fontWeight: '700' },
  messagePreview: { minHeight: 76, flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.md, borderTopWidth: 1, borderBottomWidth: 1, borderColor: colors.border },
  messageIcon: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center', borderRadius: radius.md, backgroundColor: colors.surfaceBrand },
  messageText: { flex: 1, marginHorizontal: spacing.md },
  messageName: { color: colors.text, fontSize: 14, fontWeight: '800' },
  messageBody: { color: colors.textSecondary, fontSize: 13, lineHeight: 19, marginTop: 3 },
  sectionTitleStandalone: { color: colors.text, fontSize: 18, fontWeight: '800', marginTop: spacing.xl, marginBottom: spacing.sm },
  actionList: { borderTopWidth: 1, borderColor: colors.border },
  actionRow: { minHeight: 72, flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.md, borderBottomWidth: 1, borderColor: colors.border },
  actionIcon: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center', borderRadius: radius.md, backgroundColor: colors.surface },
  actionText: { flex: 1, marginHorizontal: spacing.md },
  actionTitle: { color: colors.text, fontSize: 15, fontWeight: '800' },
  actionDescription: { color: colors.textSecondary, fontSize: 12, lineHeight: 18, marginTop: 3 },
  pressed: { opacity: 0.72 },
});
