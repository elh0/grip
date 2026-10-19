import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView, Share, StyleSheet, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Chip, ChipRow } from '@/components/chip';
import { PillButton } from '@/components/pill-button';
import { Text } from '@/components/text';
import { color, space, type } from '@/constants/theme';
import { myReferralCode, PLANS, redeemReferral, useAllowance } from '@/lib/plans';
import { allowanceLabel } from '@/lib/progress';

/** Free vs Grip, the founding offer, your invite code and a box for a friend's code. */
export default function Plans() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { allowance, load } = useAllowance();
  const [yearly, setYearly] = useState(true);
  const [code, setCode] = useState<string | null>(null);
  const [friendCode, setFriendCode] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    myReferralCode().then(setCode).catch(() => setCode(null));
  }, []);

  async function redeem() {
    setBusy(true);
    setMessage(null);
    try {
      await redeemReferral(friendCode);
      setMessage('Done. You and your friend both have a free month of Grip.');
      setFriendCode('');
      load();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'That code didn’t work.');
    }
    setBusy(false);
  }

  return (
    <View style={[styles.screen, { paddingTop: insets.top + space(3) }]}>
      <View style={styles.topRow}>
        <Text variant="label">Plans</Text>
        <Text variant="label" quiet onPress={() => router.back()} accessibilityRole="button">
          Close
        </Text>
      </View>
      <ScrollView contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + space(8) }]} keyboardShouldPersistTaps="handled">
        {allowance ? (
          <Text variant="label" quiet>
            {allowanceLabel(allowance)}
          </Text>
        ) : null}

        <View style={styles.founding}>
          <Text variant="label" style={{ color: color.black }}>
            Founding members · {PLANS.founding.limit}
          </Text>
          <Text variant="title" style={{ color: color.black }}>
            {PLANS.founding.price} {PLANS.founding.per}
          </Text>
        </View>

        <ChipRow>
          <Chip label="Yearly" on={yearly} onPress={() => setYearly(true)} />
          <Chip label="Monthly" on={!yearly} onPress={() => setYearly(false)} />
        </ChipRow>

        <View style={styles.card}>
          <Text variant="label" quiet>
            Free
          </Text>
          <Text variant="display">{PLANS.free.price}</Text>
          {PLANS.free.points.map((p) => (
            <Text key={p} quiet>
              {p}
            </Text>
          ))}
        </View>
        <View style={[styles.card, styles.grip]}>
          <Text variant="label" quiet>
            Grip
          </Text>
          <Text variant="display">
            {yearly ? PLANS.grip.yearly : PLANS.grip.monthly}
            <Text quiet>{yearly ? ' a year' : ' a month'}</Text>
          </Text>
          {yearly ? (
            <Text variant="label" quiet>
              Under £3 a month
            </Text>
          ) : null}
          {PLANS.grip.points.map((p) => (
            <Text key={p}>{p}</Text>
          ))}
          <PillButton label={allowance?.has_grip ? 'You have Grip' : 'Opens with the App Store build'} disabled onPress={() => undefined} />
        </View>

        <View style={styles.section}>
          <Text variant="label" quiet>
            Invite a friend
          </Text>
          <Text>When a new climber uses your code, you both get a month of Grip free.</Text>
          {code ? (
            <View style={styles.codeRow}>
              <Text variant="display" style={styles.code}>
                {code}
              </Text>
              <PillButton
                label="Share"
                variant="outline"
                onPress={() => Share.share({ message: `I film my climbs with grip and get three notes back. Use my code ${code} and we both get a month free. g-r-i-p.com` })}
              />
            </View>
          ) : null}
        </View>

        <View style={styles.section}>
          <Text variant="label" quiet>
            Got a code?
          </Text>
          <TextInput
            value={friendCode}
            onChangeText={(t) => setFriendCode(t.toUpperCase())}
            autoCapitalize="characters"
            autoCorrect={false}
            maxLength={6}
            placeholder="ABC123"
            placeholderTextColor={color.dark.quiet}
            style={styles.field}
          />
          <PillButton label="Use code" onPress={redeem} busy={busy} disabled={friendCode.trim().length !== 6} />
          {message ? <Text variant="label">{message}</Text> : null}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.dark.bg },
  topRow: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: space(5), paddingBottom: space(3) },
  body: { padding: space(5), gap: space(3) },
  founding: { gap: space(1), padding: space(4), borderRadius: 6, backgroundColor: color.white },
  card: { gap: space(2), padding: space(4), borderRadius: 6, backgroundColor: color.tile },
  grip: { borderWidth: 1, borderColor: color.white },
  section: { gap: space(2), paddingTop: space(4) },
  codeRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  code: { fontFamily: type.label.fontFamily, letterSpacing: 2 },
  field: { ...type.body, color: color.dark.text, minHeight: 48, paddingHorizontal: space(4), borderRadius: 6, backgroundColor: color.tile, letterSpacing: 2 },
});
