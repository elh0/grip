import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Chip, ChipRow } from '@/components/chip';
import { GymField } from '@/components/gym-picker';
import { PillButton } from '@/components/pill-button';
import { Text } from '@/components/text';
import { color, space, type } from '@/constants/theme';
import { COLOURS } from '@/lib/climb';
import { postSet } from '@/lib/gyms';

/** Snap a fresh wall: photo, gym, wall, which colours are new. */
export default function PostSet() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ gym?: string }>();
  const [gymId, setGymId] = useState<string | null>(params.gym ?? null);
  const [photo, setPhoto] = useState<string | null>(null);
  const [wall, setWall] = useState('');
  const [colours, setColours] = useState<string[]>([]);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function choose(camera: boolean) {
    const opts: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], quality: 0.8 };
    if (camera) {
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) return setError('grip needs the camera to snap the wall. You can still pick a photo.');
    }
    const res = camera ? await ImagePicker.launchCameraAsync(opts) : await ImagePicker.launchImageLibraryAsync(opts);
    if (!res.canceled && res.assets[0]) setPhoto(res.assets[0].uri);
  }

  const toggle = (id: string) =>
    setColours((cs) => (cs.includes(id) ? cs.filter((c) => c !== id) : [...cs, id]));

  async function send() {
    if (!photo || !gymId) return;
    setBusy(true);
    setError(null);
    try {
      await postSet({ gymId, wall, colours, note, photoUri: photo });
      router.back();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not post the set.');
      setBusy(false);
    }
  }

  return (
    <View style={[styles.screen, { paddingTop: insets.top + space(3) }]}>
      <View style={styles.top}>
        <Text variant="label">Post a set</Text>
        {!busy ? (
          <Text variant="label" quiet onPress={() => router.back()} accessibilityRole="button">
            Close
          </Text>
        ) : null}
      </View>
      <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
        <Pressable accessibilityRole="button" accessibilityLabel="Choose a photo" onPress={() => choose(false)} style={styles.photo}>
          {photo ? (
            <Image source={{ uri: photo }} style={StyleSheet.absoluteFill} contentFit="cover" />
          ) : (
            <Text variant="label" quiet>
              Photo of the fresh wall
            </Text>
          )}
        </Pressable>
        <ChipRow>
          <Chip label="Take photo" onPress={() => choose(true)} />
          <Chip label="Choose photo" onPress={() => choose(false)} />
        </ChipRow>
        <Text variant="label" quiet>
          Gym
        </Text>
        <GymField value={gymId} onChange={setGymId} />
        <Text variant="label" quiet>
          Wall
        </Text>
        <TextInput value={wall} onChangeText={setWall} placeholder="e.g. Cave, Slab, Comp wall" placeholderTextColor={color.dark.quiet} style={styles.input} />
        <Text variant="label" quiet>
          New colours
        </Text>
        <ChipRow>
          {COLOURS.map((c) => (
            <Chip key={c.id} label={c.id} dot={c.hex} on={colours.includes(c.id)} onPress={() => toggle(c.id)} />
          ))}
        </ChipRow>
        <TextInput
          value={note}
          onChangeText={setNote}
          placeholder="Anything worth knowing? e.g. the purple on the left is a mean V5"
          placeholderTextColor={color.dark.quiet}
          maxLength={280}
          multiline
          style={[styles.input, styles.note]}
        />
        {error ? <Text variant="label">{error}</Text> : null}
      </ScrollView>
      <View style={[styles.actions, { paddingBottom: insets.bottom + space(4) }]}>
        <PillButton label="Post" onPress={send} busy={busy} disabled={!photo || !gymId} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.dark.bg },
  top: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: space(5), paddingBottom: space(3) },
  body: { padding: space(5), gap: space(3) },
  photo: {
    width: '100%',
    aspectRatio: 4 / 5,
    borderRadius: 4,
    overflow: 'hidden',
    backgroundColor: color.tile,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.dark.rule,
  },
  input: {
    ...type.body,
    color: color.dark.text,
    minHeight: 48,
    paddingHorizontal: space(4),
    borderRadius: 6,
    backgroundColor: color.tile,
  },
  note: { minHeight: 88, paddingTop: space(3), textAlignVertical: 'top' },
  actions: { paddingHorizontal: space(5) },
});
