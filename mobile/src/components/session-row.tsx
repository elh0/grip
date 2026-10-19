import { Pressable, StyleSheet, View } from 'react-native';

import { color, space } from '@/constants/theme';
import { colourHex, placeLabel, resultLabel } from '@/lib/climb';
import { formatTime, isPending, sessionTitle, statusLabel } from '@/lib/feedback';
import { useGyms } from '@/lib/gyms';
import type { Session } from '@/lib/types';

import { Dot } from './chip';
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
  const { byId } = useGyms();
  const pending = isPending(session.status);
  const place = placeLabel(session.gym_id ? byId[session.gym_id] : undefined, session.wall);
  const tags = [session.grade, resultLabel(session.result)].filter(Boolean).join('   ');
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}>
      <View style={styles.meta}>
        <Text variant="label" quiet numberOfLines={1} style={styles.place}>
          {place ?? 'Climb'}
          {session.duration_s ? `   ${formatTime(session.duration_s)}` : ''}
        </Text>
        <Text variant="label" quiet={!pending && session.status !== 'failed'}>
          {statusLabel(session.status, notes)}
        </Text>
      </View>
      <Text variant="title" numberOfLines={1}>
        {sessionTitle(session)}
      </Text>
      {session.colour || tags ? (
        <View style={styles.tags}>
          {session.colour ? <Dot hex={colourHex(session.colour)} /> : null}
          {tags ? (
            <Text variant="label" quiet>
              {tags}
            </Text>
          ) : null}
        </View>
      ) : null}
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
  meta: { flexDirection: 'row', justifyContent: 'space-between', gap: space(3) },
  place: { flexShrink: 1 },
  tags: { flexDirection: 'row', alignItems: 'center', gap: space(2) },
});
