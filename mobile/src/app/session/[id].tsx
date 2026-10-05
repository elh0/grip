import { useEvent } from 'expo';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useVideoPlayer, VideoView } from 'expo-video';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { CueCard } from '@/components/cue-card';
import { Text } from '@/components/text';
import { Timeline } from '@/components/timeline';
import { color, space } from '@/constants/theme';
import { activeNote, formatTime, isPending, orderNotes, sessionTitle, sportLabel } from '@/lib/feedback';
import { supabase } from '@/lib/supabase';
import type { FeedbackItem, Session } from '@/lib/types';
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
  }, [id]);

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
        <Text variant="label" tone="dark" quiet onPress={confirmDelete} accessibilityRole="button">
          Delete
        </Text>
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
          {sportLabel[session.sport]}   {duration ? formatTime(duration) : ''}
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
          <CueCard
            key={item.id}
            item={item}
            frameUrl={frameUrls[item.id]}
            active={active?.id === item.id}
            onPress={() => seek(item.t_seconds)}
          />
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
});
