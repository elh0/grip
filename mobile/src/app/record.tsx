import { CameraView, useCameraPermissions, useMicrophonePermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Chip, ChipRow } from '@/components/chip';
import { GymField } from '@/components/gym-picker';
import { PillButton } from '@/components/pill-button';
import { Text } from '@/components/text';
import { color, space, type } from '@/constants/theme';
import { COLOURS, GRADES, RESULTS } from '@/lib/climb';
import type { ClimbResult } from '@/lib/types';
import { uploadSession } from '@/lib/upload';

const tip = 'Film side-on or at 45°. From directly behind, your hips are hidden.';

type Step = 'setup' | 'camera' | 'ready' | 'uploading';

export default function Record() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const camera = useRef<CameraView>(null);
  const [camPerm, requestCam] = useCameraPermissions();
  const [micPerm, requestMic] = useMicrophonePermissions();

  const [step, setStep] = useState<Step>('setup');
  const [gymId, setGymId] = useState<string | null>(null);
  const [wall, setWall] = useState('');
  const [colour, setColour] = useState<string | null>(null);
  const [grade, setGrade] = useState<string | null>(null);
  const [result, setResult] = useState<ClimbResult | null>(null);
  const [note, setNote] = useState('');
  const [videoUri, setVideoUri] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function openCamera() {
    const cam = camPerm?.granted ? camPerm : await requestCam();
    const mic = micPerm?.granted ? micPerm : await requestMic();
    if (!cam.granted || !mic.granted) {
      setError('grip needs the camera and microphone to film. You can still pick a clip.');
      return;
    }
    setStep('camera');
  }

  async function pick() {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['videos'],
      allowsEditing: true,
      videoMaxDuration: 180,
      quality: 1,
    });
    if (!result.canceled && result.assets[0]) {
      setVideoUri(result.assets[0].uri);
      setStep('ready');
    }
  }

  async function toggleRecording() {
    if (!camera.current) return;
    if (recording) {
      camera.current.stopRecording();
      return;
    }
    setRecording(true);
    try {
      const clip = await camera.current.recordAsync({ maxDuration: 180 });
      if (clip?.uri) {
        setVideoUri(clip.uri);
        setStep('ready');
      }
    } finally {
      setRecording(false);
    }
  }

  async function upload() {
    if (!videoUri) return;
    setStep('uploading');
    setError(null);
    try {
      const session = await uploadSession({ videoUri, note, gymId, wall, colour, grade, result }, setProgress);
      router.replace({ pathname: '/session/[id]', params: { id: session.id } });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed.');
      setStep('ready');
    }
  }

  if (step === 'camera') {
    return (
      <View style={styles.dark}>
        <CameraView ref={camera} style={StyleSheet.absoluteFill} mode="video" facing="back" videoQuality="1080p" />
        <View style={[styles.cameraBar, { paddingBottom: insets.bottom + space(6) }]}>
          <Text variant="label" tone="dark" style={styles.center}>
            {recording ? 'Recording' : tip}
          </Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={recording ? 'Stop recording' : 'Start recording'}
            onPress={toggleRecording}
            style={styles.shutter}>
            <View style={recording ? styles.stop : styles.dot} />
          </Pressable>
          {!recording ? (
            <Text variant="label" tone="dark" quiet onPress={() => setStep('setup')} style={styles.center}>
              Cancel
            </Text>
          ) : null}
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.screen, { paddingTop: insets.top + space(3) }]}>
      <View style={styles.topRow}>
        <Text variant="label">Film a climb</Text>
        {step !== 'uploading' ? (
          <Text variant="label" quiet onPress={() => router.back()} accessibilityRole="button">
            Close
          </Text>
        ) : null}
      </View>
      <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
        <Text quiet>{tip}</Text>
        <Text variant="label" quiet>
          Gym
        </Text>
        <GymField value={gymId} onChange={setGymId} />
        <TextInput
          value={wall}
          onChangeText={setWall}
          editable={step !== 'uploading'}
          placeholder="Wall, e.g. Cave"
          placeholderTextColor={color.dark.quiet}
          style={styles.field}
        />
        <Text variant="label" quiet>
          Colour
        </Text>
        <ChipRow>
          {COLOURS.map((c) => (
            <Chip key={c.id} label={c.id} dot={c.hex} on={colour === c.id} onPress={() => setColour(colour === c.id ? null : c.id)} />
          ))}
        </ChipRow>
        <Text variant="label" quiet>
          Grade
        </Text>
        <ChipRow>
          {GRADES.map((g) => (
            <Chip key={g} label={g} on={grade === g} onPress={() => setGrade(grade === g ? null : g)} />
          ))}
        </ChipRow>
        <Text variant="label" quiet>
          How did it go
        </Text>
        <ChipRow>
          {RESULTS.map((r) => (
            <Chip key={r.id} label={r.label} on={result === r.id} onPress={() => setResult(result === r.id ? null : r.id)} />
          ))}
        </ChipRow>
        <TextInput
          value={note}
          onChangeText={setNote}
          editable={step !== 'uploading'}
          placeholder='Anything to watch? e.g. "the crux is 0:12 to 0:18"'
          placeholderTextColor={color.dark.quiet}
          multiline
          style={styles.input}
        />
        {step === 'ready' || step === 'uploading' ? (
          <Text variant="label">{step === 'uploading' ? `Uploading ${Math.round(progress * 100)}%` : 'Clip ready'}</Text>
        ) : null}
        {step === 'uploading' ? (
          <View style={styles.bar}>
            <View style={[styles.barFill, { width: `${progress * 100}%` }]} />
          </View>
        ) : null}
        {error ? <Text variant="label">{error}</Text> : null}
      </ScrollView>
      <View style={[styles.actions, { paddingBottom: insets.bottom + space(4) }]}>
        {step === 'setup' ? (
          <>
            <PillButton label="Film" onPress={openCamera} />
            <PillButton label="Choose a clip" variant="outline" onPress={pick} />
          </>
        ) : (
          <>
            <PillButton label="Send for review" onPress={upload} busy={step === 'uploading'} />
            {step === 'ready' ? (
              <PillButton label="Start again" variant="outline" onPress={() => { setVideoUri(null); setStep('setup'); }} />
            ) : null}
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.dark.bg },
  dark: { flex: 1, backgroundColor: color.black },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: space(5),
    paddingBottom: space(3),
  },
  body: { padding: space(5), gap: space(3) },
  field: {
    ...type.body,
    color: color.dark.text,
    minHeight: 48,
    paddingHorizontal: space(4),
    borderRadius: 6,
    backgroundColor: color.tile,
  },
  input: {
    ...type.body,
    color: color.dark.text,
    minHeight: 72,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: color.dark.text,
    paddingVertical: space(2),
    textAlignVertical: 'top',
  },
  bar: { height: 2, backgroundColor: color.dark.rule },
  barFill: { height: 2, backgroundColor: color.white },
  actions: { paddingHorizontal: space(5), gap: space(3) },
  cameraBar: { position: 'absolute', left: 0, right: 0, bottom: 0, alignItems: 'center', gap: space(4), paddingHorizontal: space(5) },
  center: { textAlign: 'center' },
  shutter: { width: 76, height: 76, borderRadius: 38, borderWidth: 2, borderColor: color.white, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 60, height: 60, borderRadius: 30, backgroundColor: color.white },
  stop: { width: 28, height: 28, borderRadius: 4, backgroundColor: color.white },
});
