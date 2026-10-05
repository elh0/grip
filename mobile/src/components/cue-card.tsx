import { Image } from 'expo-image';
import { Pressable, StyleSheet, View } from 'react-native';

import { color, space } from '@/constants/theme';
import { formatTime } from '@/lib/feedback';
import type { FeedbackItem } from '@/lib/types';

import { Text } from './text';

/** One note: time and body part in mono caps, what happened, the cue, the drill. */
export function CueCard({
  item,
  frameUrl,
  active,
  onPress,
}: {
  item: FeedbackItem;
  frameUrl?: string | null;
  active?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityHint={`Jumps to ${formatTime(item.t_seconds)}`}
      style={({ pressed }) => [
        styles.card,
        { borderColor: active ? color.white : color.dark.rule },
        pressed && { opacity: 0.7 },
      ]}>
      <Text variant="label" tone="dark" quiet={!active}>
        {formatTime(item.t_seconds)}   {item.body_part}
      </Text>
      {frameUrl ? (
        <Image source={{ uri: frameUrl }} style={styles.frame} contentFit="cover" />
      ) : null}
      <Text tone="dark" quiet>
        {item.observation}
      </Text>
      <Text variant="title" tone="dark">
        {item.cue}
      </Text>
      {item.drill ? (
        <View style={styles.drill}>
          <Text variant="label" tone="dark" quiet>
            Drill
          </Text>
          <Text tone="dark" quiet>
            {item.drill}
          </Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 4,
    padding: space(4),
    gap: space(2),
    backgroundColor: color.tile,
  },
  frame: { width: '100%', aspectRatio: 16 / 9, borderRadius: 2, backgroundColor: color.black },
  drill: { gap: space(1), paddingTop: space(1) },
});
