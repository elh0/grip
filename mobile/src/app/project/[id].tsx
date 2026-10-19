import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Chip, ChipRow } from '@/components/chip';
import { GymField } from '@/components/gym-picker';
import { PillButton } from '@/components/pill-button';
import { Text } from '@/components/text';
import { color, space, type } from '@/constants/theme';
import { COLOURS, GRADES } from '@/lib/climb';
import { daysFromNow, resetLabel } from '@/lib/progress';
import { deleteProject, saveProject } from '@/lib/projects';
import { supabase } from '@/lib/supabase';
import type { Project } from '@/lib/types';

const RESET_IN = [3, 7, 14, 21, 28];

/** New or edit: where it is, what it is, your note for the next go, when the wall resets. */
export default function ProjectScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const isNew = id === 'new';
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [project, setProject] = useState<Project | null>(null);
  const [outdoors, setOutdoors] = useState(false);
  const [gymId, setGymId] = useState<string | null>(null);
  const [place, setPlace] = useState('');
  const [name, setName] = useState('');
  const [wall, setWall] = useState('');
  const [colour, setColour] = useState<string | null>(null);
  const [grade, setGrade] = useState<string | null>(null);
  const [nextNote, setNextNote] = useState('');
  const [resetsOn, setResetsOn] = useState<string | null>(null);
  const [pinned, setPinned] = useState(isNew);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isNew) return;
    supabase
      .from('projects')
      .select('*')
      .eq('id', id)
      .single<Project>()
      .then(({ data: p }) => {
        if (!p) return;
        setProject(p);
        setOutdoors(!p.gym_id && !!p.place);
        setGymId(p.gym_id);
        setPlace(p.place ?? '');
        setName(p.name ?? '');
        setWall(p.wall ?? '');
        setColour(p.colour);
        setGrade(p.grade);
        setNextNote(p.next_note ?? '');
        setResetsOn(p.resets_on);
        setPinned(p.pinned);
      });
  }, [id, isNew]);

  async function save(extra: Partial<Project> = {}) {
    setBusy(true);
    setError(null);
    try {
      await saveProject(isNew ? null : id, {
        name: name.trim() || null,
        gym_id: outdoors ? null : gymId,
        place: outdoors ? place.trim() || null : null,
        wall: wall.trim() || null,
        colour: outdoors ? null : colour,
        grade,
        next_note: nextNote.trim() || null,
        resets_on: outdoors ? null : resetsOn,
        pinned,
        ...extra,
      });
      router.back();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save.');
      setBusy(false);
    }
  }

  function confirmDelete() {
    Alert.alert('Delete this project?', 'Your climbs stay; they just lose the link.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          await deleteProject(id);
          router.back();
        },
      },
    ]);
  }

  return (
    <View style={[styles.screen, { paddingTop: insets.top + space(3) }]}>
      <View style={styles.topRow}>
        <Text variant="label">{isNew ? 'New project' : 'Project'}</Text>
        <Text variant="label" quiet onPress={() => router.back()} accessibilityRole="button">
          Close
        </Text>
      </View>
      <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
        <ChipRow>
          <Chip label="Gym" on={!outdoors} onPress={() => setOutdoors(false)} />
          <Chip label="Outdoors" on={outdoors} onPress={() => setOutdoors(true)} />
        </ChipRow>
        {outdoors ? (
          <TextInput
            value={place}
            onChangeText={setPlace}
            placeholder="Crag or boulder, e.g. Stanage Plantation"
            placeholderTextColor={color.dark.quiet}
            style={styles.field}
          />
        ) : (
          <GymField value={gymId} onChange={setGymId} />
        )}
        <TextInput
          value={wall}
          onChangeText={setWall}
          placeholder={outdoors ? 'Problem name' : 'Wall, e.g. Cave'}
          placeholderTextColor={color.dark.quiet}
          style={styles.field}
        />
        <TextInput
          value={name}
          onChangeText={setName}
          placeholder="What you call it (optional)"
          placeholderTextColor={color.dark.quiet}
          style={styles.field}
        />
        {!outdoors ? (
          <>
            <Text variant="label" quiet>
              Colour
            </Text>
            <ChipRow>
              {COLOURS.map((c) => (
                <Chip key={c.id} label={c.id} dot={c.hex} on={colour === c.id} onPress={() => setColour(colour === c.id ? null : c.id)} />
              ))}
            </ChipRow>
          </>
        ) : null}
        <Text variant="label" quiet>
          Grade
        </Text>
        <ChipRow>
          {GRADES.map((g) => (
            <Chip key={g} label={g} on={grade === g} onPress={() => setGrade(grade === g ? null : g)} />
          ))}
        </ChipRow>
        <Text variant="label" quiet>
          Next go
        </Text>
        <TextInput
          value={nextNote}
          onChangeText={setNextNote}
          placeholder="One thing to try next time. Tap Use for next go on a review note to fill this."
          placeholderTextColor={color.dark.quiet}
          multiline
          maxLength={280}
          style={styles.input}
        />
        {!outdoors ? (
          <>
            <Text variant="label" quiet>
              {resetLabel(resetsOn) ?? 'When does the wall reset?'}
            </Text>
            <ChipRow>
              {RESET_IN.map((d) => {
                const day = daysFromNow(d);
                return <Chip key={d} label={`${d} days`} on={resetsOn === day} onPress={() => setResetsOn(resetsOn === day ? null : day)} />;
              })}
              <Chip label="Not sure" on={!resetsOn} onPress={() => setResetsOn(null)} />
            </ChipRow>
          </>
        ) : null}
        <ChipRow>
          <Chip label="Show on my widget" on={pinned} onPress={() => setPinned(!pinned)} />
        </ChipRow>
        {error ? <Text variant="label">{error}</Text> : null}
      </ScrollView>
      <View style={[styles.actions, { paddingBottom: insets.bottom + space(4) }]}>
        <PillButton label="Save" onPress={() => save()} busy={busy} />
        {project?.status === 'open' ? (
          <PillButton
            label="I sent it"
            variant="outline"
            onPress={() => save({ status: 'sent', sent_at: new Date().toISOString(), pinned: false })}
          />
        ) : null}
        {project && project.status !== 'open' ? (
          <PillButton label="Back on it" variant="outline" onPress={() => save({ status: 'open', sent_at: null })} />
        ) : null}
        {project ? (
          <Text variant="label" quiet onPress={confirmDelete} accessibilityRole="button" style={styles.center}>
            Delete project
          </Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.dark.bg },
  topRow: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: space(5), paddingBottom: space(3) },
  body: { padding: space(5), gap: space(3) },
  field: { ...type.body, color: color.dark.text, minHeight: 48, paddingHorizontal: space(4), borderRadius: 6, backgroundColor: color.tile },
  input: {
    ...type.body,
    color: color.dark.text,
    minHeight: 72,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: color.dark.text,
    paddingVertical: space(2),
    textAlignVertical: 'top',
  },
  actions: { paddingHorizontal: space(5), gap: space(3) },
  center: { textAlign: 'center' },
});
