import { useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PillButton } from '@/components/pill-button';
import { Text } from '@/components/text';
import { Wordmark } from '@/components/wordmark';
import { color, space, type } from '@/constants/theme';
import { isConfigured, supabase } from '@/lib/supabase';

/** Email one-time code. Apple, Google and magic link come later (handover step 6). */
export default function SignIn() {
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function sendCode() {
    setBusy(true);
    setError(null);
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { shouldCreateUser: true },
    });
    setBusy(false);
    if (error) setError(error.message);
    else setSent(true);
  }

  async function verify() {
    setBusy(true);
    setError(null);
    const { error } = await supabase.auth.verifyOtp({
      email: email.trim(),
      token: code.trim(),
      type: 'email',
    });
    setBusy(false);
    if (error) setError(error.message);
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={[styles.screen, { paddingTop: insets.top + space(6), paddingBottom: insets.bottom + space(6) }]}>
      <Wordmark height={20} />
      <View style={styles.body}>
        <Text variant="display">Film a climb or a roll. Get three notes back.</Text>
        <Text quiet>
          {sent ? `We sent a code to ${email.trim()}.` : 'Sign in with your email. We send a code, no password.'}
        </Text>
        {!isConfigured ? (
          <Text quiet>Developer: set EXPO_PUBLIC_SUPABASE_URL and EXPO_PUBLIC_SUPABASE_ANON_KEY in mobile/.env</Text>
        ) : null}
        {sent ? (
          <TextInput
            value={code}
            onChangeText={setCode}
            placeholder="Code"
            placeholderTextColor={color.dark.quiet}
            keyboardType="number-pad"
            autoComplete="one-time-code"
            textContentType="oneTimeCode"
            maxLength={10}
            style={styles.input}
          />
        ) : (
          <TextInput
            value={email}
            onChangeText={setEmail}
            placeholder="Email"
            placeholderTextColor={color.dark.quiet}
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            textContentType="emailAddress"
            style={styles.input}
          />
        )}
        {error ? <Text variant="label">{error}</Text> : null}
      </View>
      <View style={styles.actions}>
        {sent ? (
          <>
            <PillButton label="Sign in" onPress={verify} busy={busy} disabled={code.trim().length < 6} />
            <PillButton label="Use another email" variant="outline" onPress={() => { setSent(false); setCode(''); }} />
          </>
        ) : (
          <PillButton label="Send code" onPress={sendCode} busy={busy} disabled={!/^\S+@\S+\.\S+$/.test(email.trim())} />
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.dark.bg, paddingHorizontal: space(5) },
  body: { flex: 1, justifyContent: 'center', gap: space(4) },
  input: {
    ...type.title,
    color: color.dark.text,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: color.dark.text,
    paddingVertical: space(2),
  },
  actions: { gap: space(3) },
});
