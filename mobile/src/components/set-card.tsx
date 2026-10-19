import { Image } from 'expo-image';
import { StyleSheet, View } from 'react-native';

import { color, space } from '@/constants/theme';
import { colourHex, placeLabel, timeAgo } from '@/lib/climb';
import type { Gym, SetPost } from '@/lib/types';

import { Dot } from './chip';
import { Text } from './text';

/** A climber's photo of a fresh set: where, which colours, when. */
export function SetCard({
  post,
  gym,
  photoUrl,
  mine,
  onPressGym,
  onDelete,
}: {
  post: SetPost;
  gym?: Gym;
  photoUrl?: string;
  mine?: boolean;
  onPressGym?: () => void;
  onDelete?: () => void;
}) {
  return (
    <View style={styles.card}>
      <View style={styles.photo}>
        {photoUrl ? <Image source={{ uri: photoUrl }} style={StyleSheet.absoluteFill} contentFit="cover" /> : null}
      </View>
      <View style={styles.body}>
        <View style={styles.meta}>
          <Text variant="label" onPress={onPressGym} accessibilityRole={onPressGym ? 'link' : undefined} numberOfLines={1} style={styles.place}>
            {placeLabel(gym, post.wall) ?? 'Somewhere in London'}
          </Text>
          <Text variant="label" quiet>
            {timeAgo(post.created_at)}
          </Text>
        </View>
        {post.colours.length ? (
          <View style={styles.dots}>
            {post.colours.map((c) => (
              <Dot key={c} hex={colourHex(c)} size={12} />
            ))}
          </View>
        ) : null}
        {post.note ? <Text>{post.note}</Text> : null}
        {mine && onDelete ? (
          <Text variant="label" quiet onPress={onDelete} accessibilityRole="button">
            Delete
          </Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 4,
    overflow: 'hidden',
    backgroundColor: color.tile,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.dark.rule,
  },
  photo: { width: '100%', aspectRatio: 4 / 5, backgroundColor: color.black },
  body: { padding: space(4), gap: space(2) },
  meta: { flexDirection: 'row', justifyContent: 'space-between', gap: space(3) },
  place: { flexShrink: 1 },
  dots: { flexDirection: 'row', gap: space(2) },
});
