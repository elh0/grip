import { useEvent } from 'expo';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useVideoPlayer, VideoView } from 'expo-video';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { File, Paths } from 'expo-file-system';
import { ActivityIndicator, Alert, ScrollView, Share, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { CueCard } from '@/components/cue-card';
import { NoteRating } from '@/components/note-rating';
import { Text } from '@/components/text';
import { Timeline } from '@/components/timeline';
import { color, space } from '@/constants/theme';
import { placeLabel, resultLabel } from '@/lib/climb';
import { activeNote, formatTime, isPending, orderNotes, sessionTitle } from '@/lib/feedback';
import { useGyms } from '@/lib/gyms';
import { setNextNote } from '@/lib/projects';
import { loadRatings, rateNote } from '@/lib/ratings';
import { supabase } from '@/lib/supabase';
import type { FeedbackItem, NoteRating as Rating, Session } from '@/lib/types';
import { deleteSession, signedUrl } from '@/lib/upload';

const waiting: Record<string, string> = {
  uploaded: 'In the queue.',
  analyzing: 'Watching your tape. We will let you know when the notes are in.',
};

export default function SessionScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [session, setSession] = useState<Session | null>(null);
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [frameUrls, setFrameUrls] = useState<Record<string, string>>({});
  const [ratings, setRatings] = useState<Record<string, Rating>>({});
  const { byId } = useGyms();

  const load = useCallback(async () => {
    const [{ data: s }, { data: f }] = await Promise.all([
      supabase.from('sessions').select('*').eq('id', id).single<Session>(),
      supabase.from('feedback_items').select('*').eq('session_id', id),
    ]);
    if (s) setSession(s);
    const notes = orderNotes((f as FeedbackItem[]) ?? []);
    setItems(notes);
    const urls: Record<string, string> = {};
    await Promise.all(
      notes
        .filter((n) => n.frame_path)
        .map(async (n) => {
          urls[n.id] = await signedUrl('frames', n.frame_path!).catch(() => '');
        }),
    );
    setFrameUrls(urls);
    setRatings(await loadRatings(notes.map((n) => n.id)).catch(() => ({})));
  }, [id]);

  function rate(itemId: string, vote: 'up' | 'down', why?: string) {
    const prev = ratings[itemId];
    setRatings((r) => ({ ...r, [itemId]: { feedback_item_id: itemId, user_id: prev?.user_id ?? '', vote, why: why?.trim() || null } }));
    rateNote(itemId, vote, why).catch(() => setRatings((r) => ({ ...r, [itemId]: prev })));
  }

  useEffect(() => {
    // Initial fetch, then refetch on every change; state is only set after the await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    const channel = supabase
      .channel(`session:${id}`)
      .on('postgres_changes', { event: '*', schema: 'public', table: 'sessions', filter: `id=eq.${id}` }, load)
      .on('postgres_changes', { event: '*', schema: 'public', table: 'feedback_items', filter: `session_id=eq.${id}` }, load)
      .subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
  }, [id, load]);

  const videoPath = session?.video_path;
  useEffect(() => {
    if (videoPath) signedUrl('videos', videoPath).then(setVideoUrl).catch(() => setVideoUrl(null));
  }, [videoPath]);

  const player = useVideoPlayer(videoUrl, (p) => {
    p.loop = false;
    p.timeUpdateEventInterval = 0.25;
  });
  const timeUpdate = useEvent(player, 'timeUpdate');
  const currentTime = timeUpdate?.currentTime ?? 0;
  const duration = session?.duration_s ?? player.duration ?? 0;
  const active = useMemo(() => activeNote(items, currentTime), [items, currentTime]);

  const seek = (t: number) => {
    player.seekBy(Math.max(0, t - 0.5) - player.currentTime);
    player.play();
  };

  const [nextNoteId, setNextNoteId] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);

  async function pickNextGo(item: FeedbackItem) {
    if (!session?.project_id) return;
    await setNextNote(session.project_id, item.cue).catch(() => undefined);
    setNextNoteId(item.id);
  }

  /** Download the tracked clip the worker rendered and hand it to the share sheet. */
  async function share() {
    if (!session?.share_path) return;
    setSharing(true);
    try {
      const url = await signedUrl('shares', session.share_path, 600);
      const file = new File(Paths.cache, `grip-${session.id}.mp4`);
      if (file.exists) file.delete();
      await File.downloadFileAsync(url, file);
      await Share.share({ url: file.uri });
    } catch {
      Alert.alert('Could not share', 'Try again in a moment.');
    }
    setSharing(false);
  }

  function confirmDelete() {
    if (!session) return;
    Alert.alert('Delete this session?', 'The clip and its notes are removed for good.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          await deleteSession(session, items.map((n) => n.frame_path).filter((p): p is string => !!p));
          router.back();
        },
      },
    ]);
  }

  if (!session) {
    return (
      <View style={[styles.screen, styles.centered]}>
        <ActivityIndicator color={color.white} />
      </View>
    );
  }

  return (
    <View style={styles.screen}>
      <View style={[styles.topRow, { paddingTop: insets.top + space(3) }]}>
        <Text variant="label" tone="dark" onPress={() => router.back()} accessibilityRole="button">
          Back
        </Text>
        <View style={styles.topActions}>
          {session.share_path ? (
            <Text variant="label" tone="dark" onPress={share} accessibilityRole="button">
              {sharing ? 'Getting clip' : 'Share'}
            </Text>
          ) : null}
          <Text variant="label" tone="dark" quiet onPress={confirmDelete} accessibilityRole="button">
            Delete
          </Text>
        </View>
      </View>
      {videoUrl ? (
        <VideoView player={player} style={styles.video} contentFit="contain" nativeControls={false} />
      ) : (
        <View style={[styles.video, styles.centered]}>
          <ActivityIndicator color={color.white} />
        </View>
      )}
      <Timeline items={items} duration={duration} position={currentTime} onSeek={seek} />
      <ScrollView contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + space(8) }]}>
        <Text variant="label" tone="dark" quiet>
          {[
            placeLabel(session.gym_id ? byId[session.gym_id] : undefined, session.wall) ?? 'Climb',
            session.grade,
            resultLabel(session.result),
            duration ? formatTime(duration) : '',
          ]
            .filter(Boolean)
            .join('   ')}
        </Text>
        <Text variant="title" tone="dark">
          {sessionTitle(session)}
        </Text>
        {isPending(session.status) ? (
          <Text tone="dark" quiet>
            {waiting[session.status]}
          </Text>
        ) : null}
        {session.status === 'failed' ? (
          <Text tone="dark">{session.error ?? 'We could not review this clip.'}</Text>
        ) : null}
        {session.summary ? <Text tone="dark">{session.summary}</Text> : null}
        {items.map((item) => (
          <View key={item.id} style={styles.note}>
            <CueCard
              item={item}
              frameUrl={frameUrls[item.id]}
              active={active?.id === item.id}
              onPress={() => seek(item.t_seconds)}
            />
            <NoteRating rating={ratings[item.id]} onRate={(vote, why) => rate(item.id, vote, why)} />
            {session.project_id ? (
              <Text variant="label" tone="dark" quiet={nextNoteId !== item.id} onPress={() => pickNextGo(item)} accessibilityRole="button">
                {nextNoteId === item.id ? 'On your widget for the next go' : 'Use for next go'}
              </Text>
            ) : null}
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.black },
  centered: { alignItems: 'center', justifyContent: 'center' },
  topRow: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: space(5), paddingBottom: space(3) },
  video: { width: '100%', aspectRatio: 16 / 9, backgroundColor: color.black },
  body: { padding: space(5), gap: space(3) },
  note: { gap: space(2) },
  topActions: { flexDirection: 'row', gap: space(5) },
});
