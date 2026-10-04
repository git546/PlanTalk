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

import { useConversation } from '@/context/conversation';
import { usePlantProfile } from '@/context/plant-profile';
import { fetchReply, type ChatMessage } from '@/lib/api';

export default function ChatScreen() {
  const { profile, plantContext } = usePlantProfile();
  const { messages, isLoading, nextMessageId, setMessages, resetConversation } = useConversation();
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false);
  const conversation = useRef<ScrollView>(null);

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
      const reply = await fetchReply([...history, { role: 'user', content: text }], plantContext);
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
            <View style={styles.avatar}><Text style={styles.avatarText}>🪴</Text></View>
            <View>
              <Text style={styles.title}>{profile.name}</Text>
              <Text style={styles.notice}>{profile.species} · 지금 대화할 수 있어요</Text>
            </View>
          </View>
          <Pressable
            disabled={sending}
            onPress={() => void resetConversation()}
            style={({ pressed }) => [styles.newChat, pressed && styles.pressed]}
          >
            <Text style={styles.newChatText}>새 대화</Text>
          </Pressable>
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
                <Text style={styles.sender}>{message.sender === 'user' ? '나' : profile.name}</Text>
                <Text selectable style={styles.messageText}>{message.text}</Text>
              </View>
            ))}
          </ScrollView>
        )}

        {sending && <Text accessibilityLiveRegion="polite" style={styles.status}>답변을 기다리고 있어요…</Text>}
        {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
        <View style={styles.composer}>
          <TextInput
            accessibilityLabel="메시지 입력"
            placeholder={`${profile.name}에게 메시지 보내기`}
            placeholderTextColor="#829087"
            value={draft}
            onChangeText={setDraft}
            editable={!sending}
            multiline
            maxLength={2000}
            style={styles.input}
          />
          <Pressable
            accessibilityRole="button"
            disabled={!canSend}
            onPress={() => void sendMessage()}
            style={({ pressed }) => [styles.send, !canSend && styles.disabled, pressed && styles.pressed]}
          >
            <Text style={styles.sendText}>{sending ? '…' : '↑'}</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#e8eee9' },
  container: {
    flex: 1, width: '100%', maxWidth: 480, alignSelf: 'center', backgroundColor: '#f7faf7',
    borderLeftWidth: 1, borderRightWidth: 1, borderColor: '#dde7df',
  },
  header: { padding: 16, borderBottomWidth: 1, borderBottomColor: '#dfe8e1', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#fff' },
  identity: { flexDirection: 'row', alignItems: 'center', gap: 11 },
  avatar: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: '#e2f2e6' },
  avatarText: { fontSize: 24 },
  title: { fontSize: 18, fontWeight: '800', color: '#183d2a' },
  notice: { fontSize: 12, color: '#708078', marginTop: 3 },
  newChat: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, backgroundColor: '#edf5ee' },
  newChatText: { color: '#247a52', fontSize: 12, fontWeight: '700' },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  history: { flex: 1 },
  messages: { padding: 16, gap: 14 },
  message: { maxWidth: '84%', paddingHorizontal: 14, paddingVertical: 11, borderRadius: 17 },
  userMessage: { alignSelf: 'flex-end', backgroundColor: '#245d42', borderBottomRightRadius: 5 },
  plantMessage: { alignSelf: 'flex-start', backgroundColor: '#fff', borderWidth: 1, borderColor: '#e1e9e3', borderBottomLeftRadius: 5 },
  sender: { fontSize: 11, color: '#789083', marginBottom: 4, fontWeight: '700' },
  messageText: { fontSize: 15, lineHeight: 22, color: '#20382b' },
  status: { fontSize: 12, color: '#66766d', marginHorizontal: 16, marginBottom: 4 },
  error: { color: '#b42318', fontSize: 12, marginHorizontal: 16, marginBottom: 4 },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, padding: 12, borderTopWidth: 1, borderTopColor: '#dfe8e1', backgroundColor: '#fff' },
  input: { flex: 1, minWidth: 0, minHeight: 46, maxHeight: 120, borderWidth: 1, borderColor: '#c7d6ca', borderRadius: 16, paddingHorizontal: 14, paddingVertical: 11, fontSize: 15, color: '#183d2a', backgroundColor: '#f8faf8', textAlignVertical: 'top' },
  send: { width: 46, height: 46, alignItems: 'center', justifyContent: 'center', borderRadius: 15, backgroundColor: '#247a52' },
  sendText: { color: '#fff', fontSize: 22, fontWeight: '800' },
  disabled: { backgroundColor: '#a7b9ad' },
  pressed: { opacity: 0.72 },
});
