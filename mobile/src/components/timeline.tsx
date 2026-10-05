import { Pressable, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import { useState } from 'react';

import { color, space } from '@/constants/theme';
import { timelineMarkers } from '@/lib/feedback';
import type { FeedbackItem, Severity } from '@/lib/types';

const markerHeight: Record<Severity, number> = { major: 16, moderate: 12, minor: 8 };

/** Scrub bar with a white tick at each note. Ticks are taller for bigger faults. */
export function Timeline({
  items,
  duration,
  position,
  onSeek,
}: {
  items: FeedbackItem[];
  duration: number;
  position: number;
  onSeek: (t: number) => void;
}) {
  const [width, setWidth] = useState(0);
  const markers = timelineMarkers(items, duration);
  const progress = duration > 0 ? Math.min(1, position / duration) : 0;

  return (
    <Pressable
      accessibilityRole="adjustable"
      accessibilityLabel="Timeline"
      onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)}
      onPress={(e) => width && onSeek((e.nativeEvent.locationX / width) * duration)}
      style={styles.track}>
      <View style={styles.rail} />
      <View style={[styles.played, { width: `${progress * 100}%` }]} />
      {markers.map((m) => (
        <View
          key={m.id}
          style={[
            styles.marker,
            { left: `${m.left * 100}%`, height: markerHeight[m.severity] },
          ]}
        />
      ))}
      <View style={[styles.head, { left: `${progress * 100}%` }]} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  track: { height: 32, justifyContent: 'center', marginHorizontal: space(5) },
  rail: { height: 1, backgroundColor: color.dark.rule },
  played: { position: 'absolute', height: 1, backgroundColor: color.dark.quiet },
  marker: { position: 'absolute', width: 2, marginLeft: -1, backgroundColor: color.white },
  head: {
    position: 'absolute',
    width: 9,
    height: 9,
    marginLeft: -4.5,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: color.white,
    backgroundColor: color.black,
  },
});
