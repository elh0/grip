import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';

import { Header } from '@/components/header';
import { PillButton } from '@/components/pill-button';
import { SessionRow } from '@/components/session-row';
import { Text } from '@/components/text';
import { color, space } from '@/constants/theme';
import { useAuth } from '@/lib/auth';
import { supabase } from '@/lib/supabase';
import type { Session } from '@/lib/types';

type Row = Session & { feedback_items: { count: number }[] };

export default function Sessions() {
  const router = useRouter();
  const { session: auth } = useAuth();
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const { data } = await supabase
      .from('sessions')
      .select('*, feedback_items(count)')
      .order('created_at', { ascending: false })
      .limit(100);
    setRows((data as Row[]) ?? []);
    setLoading(false);
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  // Live status: reload when any of my sessions changes.
  const userId = auth?.user.id;
  useEffect(() => {
    if (!userId) return;
    const channel = supabase
      .channel(`sessions:${userId}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'sessions', filter: `user_id=eq.${userId}` },
        () => load(),
      )
      .subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
  }, [userId, load]);

  return (
    <View style={styles.screen}>
      <Header />
      <FlatList
        data={rows}
        keyExtractor={(s) => s.id}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        renderItem={({ item }) => (
          <SessionRow
            session={item}
            notes={item.feedback_items?.[0]?.count}
            onPress={() => router.push({ pathname: '/session/[id]', params: { id: item.id } })}
          />
        )}
        ListEmptyComponent={
          loading ? null : (
            <View style={styles.empty}>
              <Text variant="title">No climbs yet.</Text>
              <Text quiet>
                Film a problem side-on or at 45 degrees. You get three notes back, each pinned to a
                moment, and you can tell us if they landed.
              </Text>
            </View>
          )
        }
        contentContainerStyle={{ paddingBottom: 96 }}
      />
      <View style={[styles.fab, { bottom: space(4) }]}>
        <PillButton label="Film a climb" onPress={() => router.push('/record')} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.dark.bg },
  empty: { padding: space(5), gap: space(2) },
  fab: { position: 'absolute', left: space(5), right: space(5) },
});
