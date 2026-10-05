import { type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { color, space, type Tone } from '@/constants/theme';

import { Wordmark } from './wordmark';

/** Small wordmark left, optional action right. */
export function Header({ tone = 'light', right }: { tone?: Tone; right?: ReactNode }) {
  const insets = useSafeAreaInsets();
  return (
    <View
      style={[
        styles.row,
        { paddingTop: insets.top + space(3), borderBottomColor: color[tone].rule },
      ]}>
      <Wordmark height={18} />
      <View>{right}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: space(5),
    paddingBottom: space(3),
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
});
