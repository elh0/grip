import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  Easing,
  runOnJS,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withDelay,
  withSequence,
  withTiming,
} from 'react-native-reanimated';
import Svg, { Path } from 'react-native-svg';

import { FINGERTIP, LETTERS, RATIO } from '@/components/wordmark';
import { color } from '@/constants/theme';

// Wordmark "Crimp" from the studio site picks: the fingertip presses the i and lets go.
const HEIGHT = 28;
const WIDTH = HEIGHT * RATIO;
const PRESS = 44 * (HEIGHT / 1019);
const ease = Easing.inOut(Easing.quad);

/** Opening screen shown once over the app after the native splash. */
export function Opening({ onDone }: { onDone: () => void }) {
  const reduced = useReducedMotion();
  const tip = useSharedValue(0);
  const fade = useSharedValue(1);

  useEffect(() => {
    const finish = () => {
      fade.value = withTiming(0, { duration: 260, easing: ease }, (ok) => {
        if (ok) runOnJS(onDone)();
      });
    };
    if (reduced) {
      fade.value = withDelay(400, withTiming(0, { duration: 260 }, (ok) => {
        if (ok) runOnJS(onDone)();
      }));
      return;
    }
    tip.value = withDelay(
      280,
      withSequence(
        withTiming(PRESS, { duration: 180, easing: ease }),
        withDelay(110, withTiming(0, { duration: 240, easing: ease }, (ok) => {
          if (ok) runOnJS(finish)();
        })),
      ),
    );
  }, [reduced, tip, fade, onDone]);

  const tipStyle = useAnimatedStyle(() => ({ transform: [{ translateY: tip.value }] }));
  const fadeStyle = useAnimatedStyle(() => ({ opacity: fade.value }));

  return (
    <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFill, styles.wrap, fadeStyle]}>
      <View style={{ width: WIDTH, height: HEIGHT }} accessibilityRole="image" accessibilityLabel="grip">
        <Svg width={WIDTH} height={HEIGHT} viewBox="32 -787 1660 1019" style={StyleSheet.absoluteFill}>
          <Path fill={color.blue} d={LETTERS} />
        </Svg>
        <Animated.View style={[StyleSheet.absoluteFill, tipStyle]}>
          <Svg width={WIDTH} height={HEIGHT} viewBox="32 -787 1660 1019">
            <Path fill="none" stroke={color.blue} strokeWidth={90} strokeLinecap="round" d={FINGERTIP} />
          </Svg>
        </Animated.View>
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: { backgroundColor: color.dark.bg, alignItems: 'center', justifyContent: 'center', zIndex: 10 },
});
