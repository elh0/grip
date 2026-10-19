import { useState } from 'react';
import { FlatList, Modal, Pressable, StyleSheet, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { color, space, type } from '@/constants/theme';
import { gymLabel, sortGyms } from '@/lib/climb';
import { useGyms } from '@/lib/gyms';

import { Text } from './text';

/** Tappable field showing the chosen gym; opens a searchable list, followed gyms first. */
export function GymField({ value, onChange }: { value: string | null; onChange: (id: string) => void }) {
  const { gyms, byId, follows } = useGyms();
  const insets = useSafeAreaInsets();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const chosen = value ? byId[value] : undefined;

  return (
    <>
      <Pressable accessibilityRole="button" onPress={() => setOpen(true)} style={styles.field}>
        <Text quiet={!chosen}>{chosen ? gymLabel(chosen) : 'Choose a gym'}</Text>
        <Text variant="label" quiet>
          Change
        </Text>
      </Pressable>
      <Modal visible={open} animationType="slide" onRequestClose={() => setOpen(false)}>
        <View style={[styles.modal, { paddingTop: insets.top + space(3) }]}>
          <View style={styles.top}>
            <Text variant="label">Gym</Text>
            <Text variant="label" quiet onPress={() => setOpen(false)} accessibilityRole="button">
              Close
            </Text>
          </View>
          <TextInput
            value={q}
            onChangeText={setQ}
            placeholder={`Search ${gyms.length} London gyms`}
            placeholderTextColor={color.dark.quiet}
            style={styles.search}
            autoCorrect={false}
          />
          <FlatList
            data={sortGyms(gyms, follows, q)}
            keyExtractor={(g) => g.id}
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={{ paddingBottom: insets.bottom + space(6) }}
            renderItem={({ item }) => (
              <Pressable
                accessibilityRole="button"
                onPress={() => {
                  onChange(item.id);
                  setOpen(false);
                }}
                style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}>
                <Text>{item.name}</Text>
                <Text quiet>
                  {item.area ?? ''}
                  {follows.has(item.id) ? '   Following' : ''}
                </Text>
              </Pressable>
            )}
          />
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  field: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    minHeight: 48,
    paddingHorizontal: space(4),
    borderRadius: 6,
    backgroundColor: color.tile,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: color.dark.rule,
  },
  modal: { flex: 1, backgroundColor: color.black },
  top: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: space(5), paddingBottom: space(3) },
  search: {
    ...type.body,
    color: color.dark.text,
    marginHorizontal: space(5),
    marginBottom: space(2),
    minHeight: 48,
    paddingHorizontal: space(4),
    borderRadius: 6,
    backgroundColor: color.tile,
  },
  row: {
    paddingVertical: space(3),
    paddingHorizontal: space(5),
    gap: 2,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: color.dark.rule,
  },
});
