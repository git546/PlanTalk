import { Tabs } from 'expo-router';

import { AppIcon } from '@/components/app-icon';
import { colors, layout } from '@/theme/tokens';

export default function AppLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.brand,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarLabelStyle: { fontSize: 12, fontWeight: '700' },
        tabBarItemStyle: { minHeight: layout.minimumTapTarget },
        tabBarStyle: {
          height: 66,
          width: '100%',
          maxWidth: layout.maxContentWidth,
          alignSelf: 'center',
          paddingTop: 6,
          paddingBottom: 8,
          borderTopColor: colors.border,
          backgroundColor: colors.surface,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: '홈',
          tabBarIcon: ({ color, focused }) => (
            <AppIcon color={color} name={focused ? 'home' : 'home-outline'} />
          ),
        }}
      />
      <Tabs.Screen
        name="plants"
        options={{
          title: '식물',
          tabBarIcon: ({ color, focused }) => (
            <AppIcon color={color} name={focused ? 'leaf' : 'leaf-outline'} />
          ),
        }}
      />
      <Tabs.Screen
        name="chat"
        options={{
          title: '대화',
          tabBarIcon: ({ color, focused }) => (
            <AppIcon
              color={color}
              name={focused ? 'chatbubble-ellipses' : 'chatbubble-ellipses-outline'}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: '설정',
          tabBarIcon: ({ color, focused }) => (
            <AppIcon color={color} name={focused ? 'settings' : 'settings-outline'} />
          ),
        }}
      />
      <Tabs.Screen name="persona" options={{ href: null }} />
      <Tabs.Screen name="water" options={{ href: null }} />
    </Tabs>
  );
}
