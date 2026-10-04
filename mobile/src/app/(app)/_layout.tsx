import { Tabs } from 'expo-router';
import { Text } from 'react-native';

export default function AppLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: '#247a52',
        tabBarInactiveTintColor: '#849188',
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
        tabBarStyle: {
          height: 66,
          width: '100%',
          maxWidth: 480,
          alignSelf: 'center',
          paddingTop: 7,
          paddingBottom: 8,
          borderTopColor: '#dbe6dd',
          backgroundColor: '#fff',
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: '홈', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 20 }}>⌂</Text> }}
      />
      <Tabs.Screen
        name="chat"
        options={{ title: '채팅', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 18 }}>●</Text> }}
      />
      <Tabs.Screen
        name="persona"
        options={{ title: '페르소나', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 19 }}>♧</Text> }}
      />
      <Tabs.Screen
        name="settings"
        options={{ title: '설정', tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 19 }}>⚙</Text> }}
      />
    </Tabs>
  );
}
