import Ionicons from '@expo/vector-icons/Ionicons';
import type { ComponentProps } from 'react';
import type { ColorValue } from 'react-native';

type IconName = ComponentProps<typeof Ionicons>['name'];

type AppIconProps = {
  name: IconName;
  size?: number;
  color: ColorValue;
};

export function AppIcon({ name, size = 22, color }: AppIconProps) {
  return <Ionicons accessibilityElementsHidden color={color} name={name} size={size} />;
}
