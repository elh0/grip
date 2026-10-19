import { Pressable, StyleSheet, View } from 'react-native';

import { color, space } from '@/constants/theme';

import { Text } from './text';

export function Dot({ hex, size = 10 }: { hex: string; size?: number }) {
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: hex,
        borderWidth: StyleSheet.hairlineWidth,
        borderColor: 'rgba(243,243,240,0.4)',
      }}
    />
  );
}

/** A mono caps toggle. On = white fill, black text. Never blue. */
export function Chip({
  label,
  on,
  dot,
  onPress,
}: {
  label: string;
  on?: boolean;
  dot?: string;
  onPress?: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: !!on }}
      onPress={onPress}
      disabled={!onPress}
      style={({ pressed }) => [styles.chip, on && styles.on, pressed && { opacity: 0.6 }]}>
      {dot ? <Dot hex={dot} /> : null}
      <Text variant="label" style={{ color: on ? color.black : color.dark.text }}>
        {label}
      </Text>
    </Pressable>
  );
}

export function ChipRow({ children }: { children: React.ReactNode }) {
  return <View style={styles.row}>{children}</View>;
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space(2),
    paddingHorizontal: space(3),
    minHeight: 38,
    borderRadius: 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.dark.rule,
  },
  on: { backgroundColor: color.white, borderColor: color.white },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: space(2) },
});
