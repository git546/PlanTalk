import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { API_URL, fetchHealth } from '@/lib/api';

type ConnectionState = 'checking' | 'connected' | 'failed';

export default function HomeScreen() {
  const [connectionState, setConnectionState] = useState<ConnectionState>('checking');
  const [message, setMessage] = useState('FastAPI 서버를 확인하고 있어요.');

  const checkConnection = useCallback(async () => {
    setConnectionState('checking');
    setMessage('FastAPI 서버를 확인하고 있어요.');

    try {
      const health = await fetchHealth();
      setConnectionState('connected');
      setMessage(`${health.service} 연결 완료`);
    } catch {
      setConnectionState('failed');
      setMessage('서버에 연결할 수 없습니다. API 주소와 실행 상태를 확인하세요.');
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    void fetchHealth()
      .then((health) => {
        if (!cancelled) {
          setConnectionState('connected');
          setMessage(`${health.service} 연결 완료`);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setConnectionState('failed');
          setMessage('서버에 연결할 수 없습니다. API 주소와 실행 상태를 확인하세요.');
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>🌱 PlanTalk</Text>
        </View>

        <Text style={styles.title}>내 반려식물과 대화하는{`\n`}조금 더 따뜻한 하루</Text>
        <Text style={styles.description}>
          React Native + Expo 모바일 앱과 FastAPI 서버의 기본 연결 환경입니다.
        </Text>

        <View style={styles.card}>
          <Text style={styles.cardLabel}>개발 서버 상태</Text>
          <View style={styles.statusRow}>
            {connectionState === 'checking' ? (
              <ActivityIndicator color="#167A55" />
            ) : (
              <View
                style={[
                  styles.statusDot,
                  connectionState === 'connected' ? styles.connected : styles.failed,
                ]}
              />
            )}
            <Text style={styles.statusText}>{message}</Text>
          </View>
          <Text selectable style={styles.apiUrl}>
            {API_URL}
          </Text>
          <Pressable
            accessibilityRole="button"
            onPress={() => void checkConnection()}
            style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
          >
            <Text style={styles.buttonText}>다시 확인</Text>
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#F4F8F3',
  },
  container: {
    flex: 1,
    justifyContent: 'center',
    padding: 24,
  },
  badge: {
    alignSelf: 'flex-start',
    borderRadius: 999,
    backgroundColor: '#DDEFE5',
    paddingHorizontal: 14,
    paddingVertical: 8,
    marginBottom: 20,
  },
  badgeText: {
    color: '#195C43',
    fontSize: 15,
    fontWeight: '700',
  },
  title: {
    color: '#16352A',
    fontSize: 34,
    fontWeight: '800',
    lineHeight: 43,
  },
  description: {
    color: '#52675F',
    fontSize: 16,
    lineHeight: 24,
    marginTop: 14,
    marginBottom: 30,
  },
  card: {
    borderRadius: 24,
    backgroundColor: '#FFFFFF',
    padding: 22,
    shadowColor: '#1E4939',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.08,
    shadowRadius: 20,
    elevation: 3,
  },
  cardLabel: {
    color: '#6B7C75',
    fontSize: 13,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 16,
  },
  statusDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  connected: {
    backgroundColor: '#25A46F',
  },
  failed: {
    backgroundColor: '#D95852',
  },
  statusText: {
    flex: 1,
    color: '#233D33',
    fontSize: 15,
    fontWeight: '600',
  },
  apiUrl: {
    color: '#75867F',
    fontSize: 12,
    marginTop: 12,
  },
  button: {
    alignItems: 'center',
    borderRadius: 14,
    backgroundColor: '#167A55',
    paddingVertical: 13,
    marginTop: 20,
  },
  buttonPressed: {
    opacity: 0.8,
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
  },
});
