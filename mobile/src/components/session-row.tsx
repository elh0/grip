import { Pressable, StyleSheet, View } from 'react-native';

import { color, space } from '@/constants/theme';
import { formatTime, isPending, sessionTitle, sportLabel, statusLabel } from '@/lib/feedback';
import type { Session } from '@/lib/types';

import { Text } from './text';

export function SessionRow({
  session,
  notes,
  onPress,
}: {
  session: Session;
  notes?: number;
  onPress: () => void;
}) {
  const pending = isPending(session.status);
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}>
      <View style={styles.meta}>
        <Text variant="label" quiet>
          {sportLabel[session.sport]}
          {session.duration_s ? `   ${formatTime(session.duration_s)}` : ''}
        </Text>
        <Text variant="label" quiet={!pending && session.status !== 'failed'}>
          {statusLabel(session.status, notes)}
        </Text>
      </View>
      <Text variant="title" numberOfLines={1}>
        {sessionTitle(session)}
      </Text>
      {session.summary ? (
        <Text quiet numberOfLines={2}>
          {session.summary}
        </Text>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    paddingVertical: space(4),
    paddingHorizontal: space(5),
    gap: space(1),
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: color.dark.rule,
  },
  meta: { flexDirection: 'row', justifyContent: 'space-between' },
});
