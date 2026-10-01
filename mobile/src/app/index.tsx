import { useRef, useState } from 'react';
import {
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

import { fetchReply, type ChatMessage } from '@/lib/api';

type Message = {
  id: number;
  sender: 'plant' | 'user';
  text: string;
};

export default function HomeScreen() {
  // 입력 중인 글과 이미 보낸 메시지를 따로 관리합니다.
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    { id: 0, sender: 'plant', text: '안녕! 오늘 하루는 어땠어?' },
  ]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false);
  const nextId = useRef(1);
  const conversation = useRef<ScrollView>(null);
  const input = useRef<TextInput>(null);

  async function sendMessage() {
    const text = draft.trim();
    if (!text || busy.current) return;
    busy.current = true;
    setSending(true);
    setError('');
    const userMessage: Message = { id: nextId.current++, sender: 'user', text };
    const history: ChatMessage[] = messages.filter((m) => m.id !== 0).slice(-20).map((m) => ({
      role: m.sender === 'user' ? 'user' : 'assistant', content: m.text,
    }));
    setMessages((previous) => [...previous, userMessage]);
    setDraft('');
    try {
      const reply = await fetchReply([...history, { role: 'user', content: text }]);
      const replyId = nextId.current++;
      setMessages((previous) => [...previous, { id: replyId, sender: 'plant', text: reply }]);
    } catch (cause) {
      setMessages((previous) => previous.filter((m) => m.id !== userMessage.id));
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
    <SafeAreaView style={styles.page}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.header}>
          <Text style={styles.title}>내 반려식물과 대화</Text>
          <Text style={styles.notice}>
            AI와 대화합니다. 최근 10번의 대화를 참고하며 새로고침하면 초기화됩니다.
          </Text>
        </View>

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
              style={[
                styles.message,
                message.sender === 'user' ? styles.userMessage : styles.plantMessage,
              ]}
            >
              <Text style={styles.sender}>{message.sender === 'user' ? '나' : '식물'}</Text>
              <Text selectable style={styles.messageText}>{message.text}</Text>
            </View>
          ))}
        </ScrollView>

        {sending && <Text accessibilityLiveRegion="polite" style={styles.notice}>답변을 기다리고 있어요…</Text>}
        {!!error && <Text accessibilityRole="alert" style={styles.notice}>{error}</Text>}
        <View style={styles.composer}>
          <TextInput
            ref={input}
            accessibilityLabel="메시지 입력"
            placeholder="메시지를 입력하세요"
            placeholderTextColor="#777"
            value={draft}
            onChangeText={setDraft}
            editable={!sending}
            multiline
            maxLength={2000}
            style={styles.input}
          />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="메시지 보내기"
            accessibilityState={{ disabled: !canSend }}
            disabled={!canSend}
            onPress={() => void sendMessage()}
            style={({ pressed }) => [
              styles.send,
              !canSend && styles.disabled,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.sendText}>{sending ? '응답 중' : '보내기'}</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#fff' },
  container: { flex: 1, width: '100%', maxWidth: 800, alignSelf: 'center' },
  header: { padding: 16, borderBottomWidth: 1, borderBottomColor: '#ddd' },
  title: { fontSize: 20, fontWeight: '600', color: '#222' },
  notice: { fontSize: 13, lineHeight: 20, color: '#666', marginTop: 6 },
  history: { flex: 1 },
  messages: { padding: 16, gap: 16 },
  message: { maxWidth: '85%', padding: 12, borderRadius: 8 },
  userMessage: { alignSelf: 'flex-end', backgroundColor: '#e5e5e5' },
  plantMessage: { alignSelf: 'flex-start', backgroundColor: '#f5f5f5' },
  sender: { fontSize: 12, color: '#666', marginBottom: 4 },
  messageText: { fontSize: 16, lineHeight: 24, color: '#222' },
  composer: {
    flexDirection: 'row', alignItems: 'flex-end', gap: 8,
    padding: 12, borderTopWidth: 1, borderTopColor: '#ddd',
  },
  input: {
    flex: 1, minWidth: 0, minHeight: 44, maxHeight: 120,
    borderWidth: 1, borderColor: '#aaa', borderRadius: 6,
    padding: 10, fontSize: 16, color: '#222', textAlignVertical: 'top',
  },
  send: {
    minHeight: 44, justifyContent: 'center', paddingHorizontal: 16,
    borderRadius: 6, backgroundColor: '#333',
  },
  sendText: { color: '#fff', fontSize: 15 },
  disabled: { backgroundColor: '#aaa' },
  pressed: { opacity: 0.7 },
});
