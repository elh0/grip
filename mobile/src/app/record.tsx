import { CameraView, useCameraPermissions, useMicrophonePermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PillButton } from '@/components/pill-button';
import { Text } from '@/components/text';
import { color, space, type } from '@/constants/theme';
import { sportLabel } from '@/lib/feedback';
import type { Sport } from '@/lib/types';
import { uploadSession } from '@/lib/upload';

const tips: Record<Sport, string> = {
  climbing: 'Film side-on or at 45°. From directly behind, your hips are hidden.',
  bjj: 'Film from the side of the mat with both of you in frame the whole time.',
};
const notePlaceholder: Record<Sport, string> = {
  climbing: 'Anything to watch? e.g. "the crux is 0:12 to 0:18"',
  bjj: 'Which one is you? e.g. "I\'m in the blue gi"',
};

type Step = 'setup' | 'camera' | 'ready' | 'uploading';

export default function Record() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const camera = useRef<CameraView>(null);
  const [camPerm, requestCam] = useCameraPermissions();
  const [micPerm, requestMic] = useMicrophonePermissions();

  const [step, setStep] = useState<Step>('setup');
  const [sport, setSport] = useState<Sport>('climbing');
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
      const session = await uploadSession({ sport, videoUri, note }, setProgress);
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
            {recording ? 'Recording' : tips[sport]}
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
    <View style={[styles.light, { paddingTop: insets.top + space(3) }]}>
      <View style={styles.topRow}>
        <Text variant="label">New session</Text>
        {step !== 'uploading' ? (
          <Text variant="label" quiet onPress={() => router.back()} accessibilityRole="button">
            Close
          </Text>
        ) : null}
      </View>
      <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
        <View style={styles.segment}>
          {(['climbing', 'bjj'] as Sport[]).map((s) => (
            <Pressable
              key={s}
              accessibilityRole="radio"
              accessibilityState={{ selected: sport === s }}
              disabled={step === 'uploading'}
              onPress={() => setSport(s)}
              style={[styles.segmentItem, sport === s && styles.segmentOn]}>
              <Text variant="label" style={{ color: sport === s ? color.white : color.black }}>
                {sportLabel[s]}
              </Text>
            </Pressable>
          ))}
        </View>
        <Text quiet>{tips[sport]}</Text>
        <TextInput
          value={note}
          onChangeText={setNote}
          editable={step !== 'uploading'}
          placeholder={notePlaceholder[sport]}
          placeholderTextColor={color.light.quiet}
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
  light: { flex: 1, backgroundColor: color.light.bg },
  dark: { flex: 1, backgroundColor: color.black },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: space(5),
    paddingBottom: space(3),
  },
  body: { padding: space(5), gap: space(4) },
  segment: { flexDirection: 'row', borderWidth: 1, borderColor: color.black, borderRadius: 999, overflow: 'hidden' },
  segmentItem: { flex: 1, alignItems: 'center', paddingVertical: space(3) },
  segmentOn: { backgroundColor: color.black },
  input: {
    ...type.body,
    color: color.light.text,
    minHeight: 72,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: color.light.text,
    paddingVertical: space(2),
    textAlignVertical: 'top',
  },
  bar: { height: 2, backgroundColor: color.light.rule },
  barFill: { height: 2, backgroundColor: color.black },
  actions: { paddingHorizontal: space(5), gap: space(3) },
  cameraBar: { position: 'absolute', left: 0, right: 0, bottom: 0, alignItems: 'center', gap: space(4), paddingHorizontal: space(5) },
  center: { textAlign: 'center' },
  shutter: { width: 76, height: 76, borderRadius: 38, borderWidth: 2, borderColor: color.white, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 60, height: 60, borderRadius: 30, backgroundColor: color.white },
  stop: { width: 28, height: 28, borderRadius: 4, backgroundColor: color.white },
});
