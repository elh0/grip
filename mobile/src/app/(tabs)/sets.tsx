import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Alert, FlatList, RefreshControl, StyleSheet, View } from 'react-native';

import { Chip, ChipRow } from '@/components/chip';
import { Header } from '@/components/header';
import { PillButton } from '@/components/pill-button';
import { SetCard } from '@/components/set-card';
import { Text } from '@/components/text';
import { color, space } from '@/constants/theme';
import { useAuth } from '@/lib/auth';
import { filterSets, type SetsFilter } from '@/lib/climb';
import { deleteSet, useGyms } from '@/lib/gyms';
import { useSets } from '@/lib/use-sets';

/** The free feed: climbers post fresh sets, you see the gyms you follow. */
export default function NewSets() {
  const router = useRouter();
  const { session } = useAuth();
  const { byId, follows } = useGyms();
  const { posts, photos, loading, load } = useSets();
  const [picked, setPicked] = useState<SetsFilter | null>(null);
  const filter: SetsFilter = picked ?? (follows.size ? 'following' : 'all');
  const shown = filterSets(posts, follows, filter);

  function confirmDelete(id: string) {
    const post = posts.find((p) => p.id === id);
    if (!post) return;
    Alert.alert('Delete this post?', 'The photo is removed for good.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => deleteSet(post).then(load) },
    ]);
  }

  return (
    <View style={styles.screen}>
      <Header
        right={
          <Text variant="label" onPress={() => router.push('/post-set')} accessibilityRole="button">
            Post a set
          </Text>
        }
      />
      <FlatList
        data={shown}
        keyExtractor={(p) => p.id}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={color.white} />}
        contentContainerStyle={styles.list}
        ListHeaderComponent={
          <ChipRow>
            <Chip label="Following" on={filter === 'following'} onPress={() => setPicked('following')} />
            <Chip label="All London" on={filter === 'all'} onPress={() => setPicked('all')} />
          </ChipRow>
        }
        renderItem={({ item }) => (
          <SetCard
            post={item}
            gym={byId[item.gym_id]}
            photoUrl={photos[item.photo_path]}
            mine={item.user_id === session?.user.id}
            onPressGym={() => router.push({ pathname: '/gym/[id]', params: { id: item.gym_id } })}
            onDelete={() => confirmDelete(item.id)}
          />
        )}
        ListEmptyComponent={
          loading ? null : (
            <View style={styles.empty}>
              {filter === 'following' && !follows.size ? (
                <>
                  <Text variant="title">Follow a gym.</Text>
                  <Text quiet>You get a nudge when someone posts a new set there.</Text>
                  <PillButton label="Find your gym" variant="outline" onPress={() => router.push('/gyms')} />
                </>
              ) : (
                <>
                  <Text variant="title">No new sets yet.</Text>
                  <Text quiet>Been in today? Snap the fresh wall and be the first to post it.</Text>
                  <PillButton label="Post a set" variant="outline" onPress={() => router.push('/post-set')} />
                </>
              )}
            </View>
          )
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.dark.bg },
  list: { padding: space(5), gap: space(4), paddingBottom: space(10) },
  empty: { gap: space(3), paddingTop: space(6) },
});
