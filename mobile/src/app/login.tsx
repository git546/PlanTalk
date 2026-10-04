import { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAuth } from '@/context/auth';

export default function LoginScreen() {
  const { signIn } = useAuth();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const canSubmit = identifier.trim().length > 0 && password.length > 0 && !isSubmitting;

  async function submit() {
    if (!canSubmit) return;
    setIsSubmitting(true);
    setError('');
    try {
      await signIn(identifier, password);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '로그인하지 못했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <SafeAreaView style={styles.page}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.center}
      >
        <View style={styles.card}>
          <View style={styles.symbol} accessibilityElementsHidden>
            <Text style={styles.symbolText}>🌱</Text>
          </View>
          <Text style={styles.brand}>PlanTalk</Text>
          <Text style={styles.title}>반려식물에게 인사해 보세요</Text>
          <Text style={styles.description}>로그인하면 나만의 식물과 대화를 시작할 수 있어요.</Text>

          <View style={styles.form}>
            <View style={styles.field}>
              <Text style={styles.label}>아이디</Text>
              <TextInput
                accessibilityLabel="아이디"
                autoCapitalize="none"
                autoCorrect={false}
                editable={!isSubmitting}
                onChangeText={setIdentifier}
                onSubmitEditing={() => undefined}
                placeholder="아이디를 입력하세요"
                placeholderTextColor="#8a948d"
                returnKeyType="next"
                style={styles.input}
                value={identifier}
              />
            </View>
            <View style={styles.field}>
              <Text style={styles.label}>비밀번호</Text>
              <TextInput
                accessibilityLabel="비밀번호"
                editable={!isSubmitting}
                onChangeText={setPassword}
                onSubmitEditing={() => void submit()}
                placeholder="비밀번호를 입력하세요"
                placeholderTextColor="#8a948d"
                returnKeyType="done"
                secureTextEntry
                style={styles.input}
                value={password}
              />
            </View>

            {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}

            <Pressable
              accessibilityRole="button"
              accessibilityState={{ disabled: !canSubmit }}
              disabled={!canSubmit}
              onPress={() => void submit()}
              style={({ pressed }) => [
                styles.button,
                !canSubmit && styles.buttonDisabled,
                pressed && styles.buttonPressed,
              ]}
            >
              <Text style={styles.buttonText}>{isSubmitting ? '로그인 중…' : '로그인'}</Text>
            </Pressable>
          </View>

          <Text style={styles.help}>현재는 팀 테스트 계정만 로그인할 수 있습니다.</Text>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#edf5ee' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  card: {
    width: '100%', maxWidth: 420, paddingHorizontal: 28, paddingVertical: 36,
    borderRadius: 24, backgroundColor: '#fff',
    shadowColor: '#183d2a', shadowOpacity: 0.08, shadowRadius: 24,
    shadowOffset: { width: 0, height: 10 }, elevation: 3,
  },
  symbol: {
    width: 64, height: 64, alignSelf: 'center', alignItems: 'center', justifyContent: 'center',
    borderRadius: 20, backgroundColor: '#e2f2e6', marginBottom: 16,
  },
  symbolText: { fontSize: 34 },
  brand: { textAlign: 'center', color: '#247a52', fontSize: 16, fontWeight: '700' },
  title: {
    marginTop: 8, textAlign: 'center', color: '#183d2a', fontSize: 24,
    lineHeight: 32, fontWeight: '700',
  },
  description: { marginTop: 8, textAlign: 'center', color: '#68766d', fontSize: 14, lineHeight: 21 },
  form: { marginTop: 28, gap: 16 },
  field: { gap: 7 },
  label: { color: '#334d3d', fontSize: 14, fontWeight: '600' },
  input: {
    minHeight: 50, borderWidth: 1, borderColor: '#cbd9ce', borderRadius: 12,
    paddingHorizontal: 14, color: '#173b27', backgroundColor: '#fbfdfb', fontSize: 16,
  },
  error: { color: '#b42318', fontSize: 13, lineHeight: 19 },
  button: {
    minHeight: 52, alignItems: 'center', justifyContent: 'center', borderRadius: 12,
    backgroundColor: '#247a52', marginTop: 4,
  },
  buttonDisabled: { backgroundColor: '#9bb4a4' },
  buttonPressed: { opacity: 0.82 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  help: { marginTop: 22, textAlign: 'center', color: '#7a867e', fontSize: 12 },
});
