import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { AuthProvider, useAuth } from '@/context/auth';
import { ConversationProvider } from '@/context/conversation';
import { PlantProfileProvider } from '@/context/plant-profile';

function RootNavigator() {
  const { session, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator color="#247a52" size="large" />
        <Text style={styles.loadingText}>로그인 정보를 확인하고 있어요.</Text>
      </View>
    );
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={!!session}>
        <Stack.Screen name="(app)" />
      </Stack.Protected>
      <Stack.Protected guard={!session}>
        <Stack.Screen name="login" />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <PlantProfileProvider>
        <ConversationProvider>
          <RootNavigator />
        </ConversationProvider>
      </PlantProfileProvider>
      <StatusBar style="dark" />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    backgroundColor: '#f4f8f4',
  },
  loadingText: { color: '#426052', fontSize: 14 },
});
