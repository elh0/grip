import { ActivityIndicator, Pressable, StyleSheet, type ViewStyle } from 'react-native';

import { color, space, type Tone } from '@/constants/theme';

import { Text } from './text';

/** Solid on the screen's tone: black on light screens, white on dark. Never blue. */
export function PillButton({
  label,
  onPress,
  tone = 'light',
  variant = 'solid',
  disabled,
  busy,
  style,
}: {
  label: string;
  onPress: () => void;
  tone?: Tone;
  variant?: 'solid' | 'outline';
  disabled?: boolean;
  busy?: boolean;
  style?: ViewStyle;
}) {
  const ink = tone === 'light' ? color.black : color.white;
  const paper = tone === 'light' ? color.white : color.black;
  const solid = variant === 'solid';
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!disabled, busy: !!busy }}
      onPress={onPress}
      disabled={disabled || busy}
      style={({ pressed }) => [
        styles.base,
        { borderColor: ink, backgroundColor: solid ? ink : 'transparent' },
        (pressed || disabled) && { opacity: 0.5 },
        style,
      ]}>
      {busy ? (
        <ActivityIndicator color={solid ? paper : ink} />
      ) : (
        <Text variant="label" style={{ color: solid ? paper : ink }}>
          {label}
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 48,
    paddingHorizontal: space(6),
    borderRadius: 999,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
