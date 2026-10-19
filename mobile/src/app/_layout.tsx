import { DMMono_400Regular } from '@expo-google-fonts/dm-mono';
import { HostGrotesk_400Regular } from '@expo-google-fonts/host-grotesk';
import { useFonts } from 'expo-font';
import { Stack, useRouter, useSegments } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useState } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { Opening } from '@/components/opening';
import { color } from '@/constants/theme';
import { AuthProvider, useAuth } from '@/lib/auth';
import { GymsProvider } from '@/lib/gyms';

SplashScreen.preventAutoHideAsync().catch(() => undefined);

function Gate() {
  const { session, ready } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    const onSignIn = segments[0] === 'sign-in';
    if (!session && !onSignIn) router.replace('/sign-in');
    else if (session && onSignIn) router.replace('/');
  }, [ready, session, segments, router]);

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: color.dark.bg },
      }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="sign-in" />
      <Stack.Screen name="record" options={{ presentation: 'fullScreenModal' }} />
      <Stack.Screen name="post-set" options={{ presentation: 'fullScreenModal' }} />
      <Stack.Screen name="session/[id]" />
      <Stack.Screen name="gym/[id]" />
    </Stack>
  );
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts({ HostGrotesk_400Regular, DMMono_400Regular });
  const [opening, setOpening] = useState(true);
  const endOpening = useCallback(() => setOpening(false), []);

  useEffect(() => {
    if (fontsLoaded) SplashScreen.hideAsync().catch(() => undefined);
  }, [fontsLoaded]);

  if (!fontsLoaded) return null;
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <StatusBar style="light" />
        <GymsProvider>
          <Gate />
        </GymsProvider>
        {opening && <Opening onDone={endOpening} />}
      </AuthProvider>
    </SafeAreaProvider>
  );
}
