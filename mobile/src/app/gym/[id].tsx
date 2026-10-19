import * as Linking from 'expo-linking';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { FlatList, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Chip, ChipRow } from '@/components/chip';
import { PillButton } from '@/components/pill-button';
import { SetCard } from '@/components/set-card';
import { Text } from '@/components/text';
import { color, space } from '@/constants/theme';
import { useAuth } from '@/lib/auth';
import { useGyms } from '@/lib/gyms';
import { useSets } from '@/lib/use-sets';

export default function GymScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { session } = useAuth();
  const { byId, follows, toggleFollow } = useGyms();
  const { posts, photos, loading } = useSets(id);
  const gym = byId[id];
  const post = () => router.push({ pathname: '/post-set', params: { gym: id } });

  return (
    <View style={styles.screen}>
      <View style={[styles.top, { paddingTop: insets.top + space(3) }]}>
        <Text variant="label" onPress={() => router.back()} accessibilityRole="button">
          Back
        </Text>
        <Text variant="label" onPress={post} accessibilityRole="button">
          Post a set
        </Text>
      </View>
      <FlatList
        data={posts}
        keyExtractor={(p) => p.id}
        contentContainerStyle={[styles.list, { paddingBottom: insets.bottom + space(10) }]}
        ListHeaderComponent={
          <View style={styles.head}>
            <Text variant="label" quiet>
              {gym?.area ?? 'London'}
            </Text>
            <Text variant="display">{gym?.name ?? ''}</Text>
            <ChipRow>
              <Chip label={follows.has(id) ? 'Following' : 'Follow for new sets'} on={follows.has(id)} onPress={() => toggleFollow(id)} />
              {gym?.website ? <Chip label="Website" onPress={() => Linking.openURL(gym.website!)} /> : null}
              {gym?.instagram ? (
                <Chip label="Instagram" onPress={() => Linking.openURL(`https://instagram.com/${gym.instagram}`)} />
              ) : null}
            </ChipRow>
          </View>
        }
        renderItem={({ item }) => (
          <SetCard post={item} gym={gym} photoUrl={photos[item.photo_path]} mine={item.user_id === session?.user.id} />
        )}
        ListEmptyComponent={
          loading ? null : (
            <View style={styles.empty}>
              <Text variant="title">Be the first to post a set.</Text>
              <Text quiet>Climbed here this week? A photo of the fresh wall helps everyone plan their session.</Text>
              <PillButton label="Post a set" variant="outline" onPress={post} />
            </View>
          )
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.dark.bg },
  top: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: space(5), paddingBottom: space(3) },
  list: { paddingHorizontal: space(5), gap: space(4) },
  head: { gap: space(3), paddingTop: space(2), paddingBottom: space(2) },
  empty: { gap: space(3) },
});
