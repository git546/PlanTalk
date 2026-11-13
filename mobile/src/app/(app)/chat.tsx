import { useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AppIcon } from '@/components/app-icon';
import { useConversation } from '@/context/conversation';
import { usePlantCatalog } from '@/context/plant-catalog';
import { usePlantProfile } from '@/context/plant-profile';
import { fetchReply, type ChatMessage } from '@/lib/api';
import { colors, layout, radius, spacing } from '@/theme/tokens';

export default function ChatScreen() {
  const { profile, plantContext } = usePlantProfile();
  const { selectedPlant } = usePlantCatalog();
  const { messages, isLoading, nextMessageId, setMessages, resetConversation } = useConversation();
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false);
  const conversation = useRef<ScrollView>(null);
  const chatPlantName = selectedPlant?.name ?? profile.name;
  const chatPlantSpecies = selectedPlant?.species ?? profile.species;
  const isCalibrated = !!selectedPlant
    && selectedPlant.setupWeightG !== null
    && selectedPlant.targetWetWeightG !== null
    && selectedPlant.wateringTriggerWeightG !== null;

  async function sendMessage() {
    const text = draft.trim();
    if (!text || busy.current) return;
    busy.current = true;
    setSending(true);
    setError('');
    const userMessage = { id: nextMessageId(), sender: 'user' as const, text };
    const history: ChatMessage[] = messages.filter((message) => message.id !== 0).slice(-20).map((message) => ({
      role: message.sender === 'user' ? 'user' : 'assistant',
      content: message.text,
    }));
    setMessages((previous) => [...previous, userMessage]);
    setDraft('');
    try {
      const reply = await fetchReply(
        [...history, { role: 'user', content: text }],
        {
          ...plantContext,
          ...(selectedPlant ? {
            id: selectedPlant.id,
            name: selectedPlant.name,
            species: selectedPlant.species,
          } : {}),
        },
      );
      setMessages((previous) => [
        ...previous,
        { id: nextMessageId(), sender: 'plant', text: reply },
      ]);
    } catch (cause) {
      setMessages((previous) => previous.filter((message) => message.id !== userMessage.id));
      setDraft(text);
      setError(cause instanceof Error && cause.name !== 'AbortError'
        ? cause.message : '응답 시간이 초과됐어요. 다시 보내 주세요.');
    } finally {
      busy.current = false;
      setSending(false);
    }
  }

  const canSend = draft.trim().length > 0 && !sending;

  return (
    <SafeAreaView edges={['top']} style={styles.page}>
      <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={styles.header}>
          <View style={styles.identity}>
            <View style={styles.avatar}>
              <AppIcon color={colors.brand} name="leaf" size={23} />
            </View>
            <View>
              <Text style={styles.title}>{chatPlantName}</Text>
              <Text style={styles.notice}>{chatPlantSpecies} · 대화 중</Text>
            </View>
          </View>
          <Pressable
            accessibilityLabel="새 대화 시작"
            accessibilityRole="button"
            disabled={sending}
            onPress={() => void resetConversation()}
            style={({ pressed }) => [styles.newChat, pressed && styles.pressed]}
          >
            <Text style={styles.newChatText}>새 대화</Text>
          </Pressable>
        </View>

        <View style={styles.contextBar}>
          <AppIcon
            color={isCalibrated ? colors.brand : colors.warningText}
            name={isCalibrated ? 'checkmark-circle-outline' : 'alert-circle-outline'}
            size={18}
          />
          <Text style={styles.contextText}>
            {isCalibrated
              ? '화분 기준값이 대화의 보조 정보로 연결되어 있어요.'
              : '초기 무게 기준이 없어 현재는 대화 기록 중심으로 답해요.'}
          </Text>
        </View>

        {isLoading ? (
          <View style={styles.loading}><ActivityIndicator color="#247a52" /></View>
        ) : (
          <ScrollView
            ref={conversation}
            style={styles.history}
            contentContainerStyle={styles.messages}
            keyboardShouldPersistTaps="handled"
            onContentSizeChange={() => conversation.current?.scrollToEnd({ animated: true })}
          >
            {messages.map((message) => (
              <View
                key={message.id}
                style={[styles.message, message.sender === 'user' ? styles.userMessage : styles.plantMessage]}
              >
                <Text style={[styles.sender, message.sender === 'user' && styles.userSender]}>
                  {message.sender === 'user' ? '나' : chatPlantName}
                </Text>
                <Text
                  selectable
                  style={[styles.messageText, message.sender === 'user' && styles.userMessageText]}
                >
                  {message.text}
                </Text>
              </View>
            ))}
          </ScrollView>
        )}

        {sending && <Text accessibilityLiveRegion="polite" style={styles.status}>답변을 기다리고 있어요…</Text>}
        {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
        <View style={styles.composer}>
          <TextInput
            accessibilityLabel="메시지 입력"
            placeholder={`${chatPlantName}에게 메시지 보내기`}
            placeholderTextColor="#829087"
            value={draft}
            onChangeText={setDraft}
            editable={!sending}
            multiline
            maxLength={2000}
            style={styles.input}
          />
          <Pressable
            accessibilityLabel="메시지 보내기"
            accessibilityRole="button"
            accessibilityState={{ disabled: !canSend }}
            disabled={!canSend}
            onPress={() => void sendMessage()}
            style={({ pressed }) => [styles.send, !canSend && styles.disabled, pressed && styles.pressed]}
          >
            {sending
              ? <Text style={styles.sendText}>…</Text>
              : <AppIcon color={colors.surface} name="arrow-up" size={21} />}
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.canvas },
  container: {
    flex: 1, width: '100%', maxWidth: layout.maxContentWidth, alignSelf: 'center',
    backgroundColor: colors.canvas,
  },
  header: { minHeight: 72, paddingHorizontal: spacing.lg, borderBottomWidth: 1, borderBottomColor: colors.border, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: colors.surface },
  identity: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  avatar: { width: 44, height: 44, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surfaceBrand },
  title: { fontSize: 18, fontWeight: '800', color: colors.text },
  notice: { fontSize: 12, color: colors.textMuted, marginTop: 3 },
  newChat: { minHeight: 44, justifyContent: 'center', paddingHorizontal: spacing.md, borderRadius: radius.md, backgroundColor: colors.surfaceBrand },
  newChatText: { color: colors.brand, fontSize: 12, fontWeight: '800' },
  contextBar: { minHeight: 42, flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.surfaceMuted },
  contextText: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  history: { flex: 1 },
  messages: { padding: spacing.lg, gap: spacing.md },
  message: { maxWidth: '86%', paddingHorizontal: 14, paddingVertical: 11, borderRadius: radius.lg },
  userMessage: { alignSelf: 'flex-end', backgroundColor: colors.brandStrong, borderBottomRightRadius: 4 },
  plantMessage: { alignSelf: 'flex-start', backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderBottomLeftRadius: 4 },
  sender: { fontSize: 11, color: colors.textMuted, marginBottom: 4, fontWeight: '700' },
  userSender: { color: '#CFE1D5' },
  messageText: { fontSize: 15, lineHeight: 22, color: colors.text },
  userMessageText: { color: colors.surface },
  status: { fontSize: 12, color: colors.textSecondary, marginHorizontal: spacing.lg, marginBottom: spacing.xs },
  error: { color: colors.danger, fontSize: 12, marginHorizontal: spacing.lg, marginBottom: spacing.xs },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: spacing.sm, padding: spacing.md, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.surface },
  input: { flex: 1, minWidth: 0, minHeight: 46, maxHeight: 120, borderWidth: 1, borderColor: colors.borderStrong, borderRadius: radius.lg, paddingHorizontal: 14, paddingVertical: 11, fontSize: 15, color: colors.text, backgroundColor: colors.surfaceMuted, textAlignVertical: 'top' },
  send: { width: 46, height: 46, alignItems: 'center', justifyContent: 'center', borderRadius: radius.md, backgroundColor: colors.brand },
  sendText: { color: colors.surface, fontSize: 22, fontWeight: '800' },
  disabled: { backgroundColor: colors.disabled },
  pressed: { opacity: 0.72 },
});
