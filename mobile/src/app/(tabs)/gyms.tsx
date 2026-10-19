import { useRouter } from 'expo-router';
import { useState } from 'react';
import { FlatList, Pressable, StyleSheet, TextInput, View } from 'react-native';

import { Chip } from '@/components/chip';
import { Header } from '@/components/header';
import { PillButton } from '@/components/pill-button';
import { Text } from '@/components/text';
import { color, space, type } from '@/constants/theme';
import { sortGyms } from '@/lib/climb';
import { requestGym, useGyms } from '@/lib/gyms';

/** Every London gym. Follow one to get new-set alerts. */
export default function Gyms() {
  const router = useRouter();
  const { gyms, follows, toggleFollow } = useGyms();
  const [q, setQ] = useState('');
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [area, setArea] = useState('');
  const [sent, setSent] = useState(false);

  async function send() {
    if (!name.trim()) return;
    await requestGym(name, area).catch(() => undefined);
    setSent(true);
    setAdding(false);
    setName('');
    setArea('');
  }

  return (
    <View style={styles.screen}>
      <Header right={<Text variant="label" quiet>{`London   ${follows.size} followed`}</Text>} />
      <FlatList
        data={sortGyms(gyms, follows, q)}
        keyExtractor={(g) => g.id}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ paddingBottom: space(10) }}
        ListHeaderComponent={
          <View style={styles.head}>
            <View style={styles.soon}>
              <Text variant="label" quiet>
                Coming soon
              </Text>
              <Text variant="title">Wall maps</Text>
              <Text quiet>
                Scan a fresh set with your phone and everyone gets a map of every problem on it.
              </Text>
            </View>
            <TextInput
              value={q}
              onChangeText={setQ}
              placeholder={`Search ${gyms.length} gyms`}
              placeholderTextColor={color.dark.quiet}
              style={styles.input}
              autoCorrect={false}
            />
          </View>
        }
        renderItem={({ item }) => (
          <Pressable
            accessibilityRole="button"
            onPress={() => router.push({ pathname: '/gym/[id]', params: { id: item.id } })}
            style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}>
            <View style={styles.rowText}>
              <Text numberOfLines={1}>{item.name}</Text>
              {item.area ? <Text quiet numberOfLines={1}>{item.area}</Text> : null}
            </View>
            <Chip
              label={follows.has(item.id) ? 'Following' : 'Follow'}
              on={follows.has(item.id)}
              onPress={() => toggleFollow(item.id)}
            />
          </Pressable>
        )}
        ListFooterComponent={
          <View style={styles.add}>
            {sent ? <Text quiet>Thanks. We will add it soon.</Text> : null}
            {adding ? (
              <>
                <TextInput value={name} onChangeText={setName} placeholder="Gym name" placeholderTextColor={color.dark.quiet} style={styles.input} />
                <TextInput value={area} onChangeText={setArea} placeholder="Area (optional)" placeholderTextColor={color.dark.quiet} style={styles.input} />
                <PillButton label="Send" onPress={send} disabled={!name.trim()} />
              </>
            ) : (
              <PillButton label="Add your gym" variant="outline" onPress={() => { setSent(false); setAdding(true); }} />
            )}
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.dark.bg },
  head: { padding: space(5), gap: space(4) },
  soon: {
    padding: space(4),
    gap: space(1),
    borderRadius: 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.dark.rule,
    borderStyle: 'dashed',
  },
  input: {
    ...type.body,
    color: color.dark.text,
    minHeight: 48,
    paddingHorizontal: space(4),
    borderRadius: 6,
    backgroundColor: color.tile,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space(3),
    paddingVertical: space(3),
    paddingHorizontal: space(5),
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: color.dark.rule,
  },
  rowText: { flex: 1, gap: 2 },
  add: { padding: space(5), gap: space(3) },
});
