import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';

import { Dot } from '@/components/chip';
import { Header } from '@/components/header';
import { PillButton } from '@/components/pill-button';
import { Text } from '@/components/text';
import { color, space } from '@/constants/theme';
import { colourHex } from '@/lib/climb';
import { useGyms } from '@/lib/gyms';
import { useAllowance } from '@/lib/plans';
import { allowanceLabel, gradePyramid, projectTitle, resetLabel } from '@/lib/progress';
import { projectPlace, useProjects } from '@/lib/projects';
import { supabase } from '@/lib/supabase';
import type { Project, Session } from '@/lib/types';

type Climb = Pick<Session, 'id' | 'grade' | 'result' | 'project_id'>;

/** You: your project, the rest of your projects, your sends as a grade pyramid, your plan. */
export default function You() {
  const router = useRouter();
  const { byId } = useGyms();
  const { projects, current, loading, load } = useProjects();
  const { allowance, load: loadAllowance } = useAllowance();
  const [climbs, setClimbs] = useState<Climb[]>([]);

  const loadClimbs = useCallback(async () => {
    const { data } = await supabase.from('sessions').select('id, grade, result, project_id').limit(1000);
    setClimbs((data as Climb[]) ?? []);
  }, []);
  useFocusEffect(
    useCallback(() => {
      loadClimbs();
    }, [loadClimbs]),
  );

  const pyramid = gradePyramid(climbs);
  const widest = Math.max(1, ...pyramid.map((r) => r.sends));
  const sends = pyramid.reduce((n, r) => n + r.sends, 0);
  const others = projects.filter((p) => p.id !== current?.id && p.status !== 'dropped');
  const open = (p: Project) => router.push({ pathname: '/project/[id]', params: { id: p.id } });

  return (
    <View style={styles.screen}>
      <Header
        right={
          <Text variant="label" quiet onPress={() => supabase.auth.signOut()} accessibilityRole="button">
            Sign out
          </Text>
        }
      />
      <ScrollView
        contentContainerStyle={styles.body}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={() => {
              load();
              loadClimbs();
              loadAllowance();
            }}
          />
        }>
        <Text variant="label" quiet>
          Your project
        </Text>
        {current ? (
          <Pressable accessibilityRole="button" onPress={() => open(current)} style={({ pressed }) => [styles.card, pressed && { opacity: 0.7 }]}>
            <View style={styles.row}>
              {current.colour ? <Dot hex={colourHex(current.colour)} size={12} /> : null}
              <Text variant="title" style={{ flex: 1 }}>
                {projectTitle(current)}
              </Text>
              {current.grade ? <Text variant="label">{current.grade}</Text> : null}
            </View>
            {projectPlace(current, byId) ? <Text quiet>{projectPlace(current, byId)}</Text> : null}
            <View style={styles.next}>
              <Text variant="label" quiet>
                Next go
              </Text>
              <Text>{current.next_note ?? 'Pick a note from a review, or write your own.'}</Text>
            </View>
            {resetLabel(current.resets_on) ? (
              <Text variant="label" quiet>
                {resetLabel(current.resets_on)}
              </Text>
            ) : null}
          </Pressable>
        ) : (
          <View style={styles.card}>
            <Text variant="title">Pick a boulder to work on.</Text>
            <Text quiet>
              In a gym or outdoors. Link your goes to it, keep one note for the next go, and see it on
              your home screen widget.
            </Text>
          </View>
        )}
        <PillButton label="New project" variant="outline" onPress={() => router.push({ pathname: '/project/[id]', params: { id: 'new' } })} />

        {others.length ? (
          <View style={styles.section}>
            <Text variant="label" quiet>
              Projects
            </Text>
            {others.map((p) => (
              <Pressable key={p.id} accessibilityRole="button" onPress={() => open(p)} style={styles.listRow}>
                {p.colour ? <Dot hex={colourHex(p.colour)} /> : null}
                <Text style={{ flex: 1 }} numberOfLines={1}>
                  {projectTitle(p)}
                </Text>
                <Text variant="label" quiet>
                  {p.status === 'sent' ? 'Sent' : p.grade ?? ''}
                </Text>
              </Pressable>
            ))}
          </View>
        ) : null}

        <View style={styles.section}>
          <View style={styles.row}>
            <Text variant="label" quiet style={{ flex: 1 }}>
              Sends
            </Text>
            <Text variant="label" quiet>
              {sends} {sends === 1 ? 'climb' : 'climbs'}
            </Text>
          </View>
          {pyramid.length ? (
            pyramid.map((r) => (
              <View key={r.grade} style={styles.pyramidRow} accessibilityLabel={`${r.grade}: ${r.sends} sends, ${r.flashes} flashed`}>
                <Text variant="label" style={styles.grade}>
                  {r.grade}
                </Text>
                <View style={styles.barTrack}>
                  <View style={[styles.bar, { width: `${(r.sends / widest) * 100}%` }]}>
                    <View style={[styles.flash, { width: `${(r.flashes / r.sends) * 100}%` }]} />
                  </View>
                </View>
                <Text variant="label" quiet style={styles.count}>
                  {r.sends}
                </Text>
              </View>
            ))
          ) : (
            <Text quiet>Tag a climb as sent or flashed and it builds your pyramid here.</Text>
          )}
          {pyramid.length ? (
            <Text variant="label" quiet>
              Solid is flashed, outline is sent
            </Text>
          ) : null}
        </View>

        <Pressable accessibilityRole="button" onPress={() => router.push('/plans')} style={styles.listRow}>
          <Text style={{ flex: 1 }}>{allowance?.has_grip ? 'Grip' : 'Free'}</Text>
          <Text variant="label" quiet>
            {allowanceLabel(allowance) ?? ''}
          </Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={() => router.push('/plans')} style={styles.listRow}>
          <Text style={{ flex: 1 }}>Invite a friend</Text>
          <Text variant="label" quiet>
            You both get a month free
          </Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.dark.bg },
  body: { padding: space(5), gap: space(3), paddingBottom: space(12) },
  card: { gap: space(2), padding: space(4), borderRadius: 6, backgroundColor: color.tile },
  row: { flexDirection: 'row', alignItems: 'center', gap: space(2) },
  next: { gap: space(1), paddingTop: space(1) },
  section: { gap: space(2), paddingTop: space(4) },
  listRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space(3),
    minHeight: 48,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: color.dark.rule,
  },
  pyramidRow: { flexDirection: 'row', alignItems: 'center', gap: space(3), height: 22 },
  grade: { width: 32 },
  count: { width: 24, textAlign: 'right' },
  barTrack: { flex: 1, alignItems: 'center' },
  bar: { height: 14, borderWidth: 1, borderColor: color.white, borderRadius: 2, overflow: 'hidden', minWidth: 14 },
  flash: { height: '100%', backgroundColor: color.white },
});
