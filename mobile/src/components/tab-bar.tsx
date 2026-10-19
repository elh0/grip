import type { BottomTabBarProps } from 'expo-router/js-tabs';
import { Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { color, space } from '@/constants/theme';

import { Text } from './text';

/** Three mono caps labels; the current one is white with a dot above it. */
export function TabBar({ state, descriptors, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.bar, { paddingBottom: insets.bottom }]}>
      {state.routes.map((route, i) => {
        const focused = state.index === i;
        const label = descriptors[route.key].options.title ?? route.name;
        return (
          <Pressable
            key={route.key}
            accessibilityRole="tab"
            accessibilityState={{ selected: focused }}
            onPress={() => {
              const e = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
              if (!focused && !e.defaultPrevented) navigation.navigate(route.name);
            }}
            style={styles.tab}>
            <View style={[styles.dot, { opacity: focused ? 1 : 0 }]} />
            <Text variant="label" style={{ color: focused ? color.white : 'rgba(243,243,240,0.32)' }}>
              {label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    backgroundColor: color.black,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: color.dark.rule,
  },
  tab: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space(2), height: 60 },
  dot: { width: 5, height: 5, borderRadius: 3, backgroundColor: color.white },
});
