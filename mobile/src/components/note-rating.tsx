import { useState } from 'react';
import { StyleSheet, TextInput, View } from 'react-native';

import { color, space, type } from '@/constants/theme';
import type { NoteRating as Rating } from '@/lib/types';

import { Chip, ChipRow } from './chip';
import { Text } from './text';

/** Did this note land? Thumbs up or down, then an optional reason. */
export function NoteRating({
  rating,
  onRate,
}: {
  rating?: Rating;
  onRate: (vote: 'up' | 'down', why?: string) => void;
}) {
  const [why, setWhy] = useState(rating?.why ?? '');
  const [editing, setEditing] = useState(false);
  const vote = rating?.vote;

  function pick(v: 'up' | 'down') {
    onRate(v, why);
    setEditing(true);
  }

  return (
    <View style={styles.wrap}>
      <ChipRow>
        <Chip label="Helped" on={vote === 'up'} onPress={() => pick('up')} />
        <Chip label="Not for me" on={vote === 'down'} onPress={() => pick('down')} />
      </ChipRow>
      {vote && editing ? (
        <View style={styles.why}>
          <TextInput
            value={why}
            onChangeText={setWhy}
            placeholder={vote === 'up' ? 'What clicked? (optional)' : 'What was off? (optional)'}
            placeholderTextColor={color.dark.quiet}
            maxLength={500}
            style={styles.input}
            onSubmitEditing={() => {
              onRate(vote, why);
              setEditing(false);
            }}
            returnKeyType="done"
          />
          <Text
            variant="label"
            onPress={() => {
              onRate(vote, why);
              setEditing(false);
            }}
            accessibilityRole="button">
            Save
          </Text>
        </View>
      ) : rating?.why ? (
        <Text quiet onPress={() => setEditing(true)}>
          {rating.why}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: space(2), paddingBottom: space(2) },
  why: { flexDirection: 'row', alignItems: 'center', gap: space(3) },
  input: {
    ...type.body,
    flex: 1,
    color: color.dark.text,
    minHeight: 44,
    paddingHorizontal: space(3),
    borderRadius: 6,
    backgroundColor: color.tile,
  },
});
