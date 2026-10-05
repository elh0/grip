import Svg, { Path } from 'react-native-svg';

import { color } from '@/constants/theme';

const D =
  'M10 68H90M17 68V54a7 7 0 0 1 14 0V68M35 68V46a7 7 0 0 1 14 0V68M53 68V46a7 7 0 0 1 14 0V68M71 68V54a7 7 0 0 1 14 0V68';

/** The crimp: icon and splash only, never next to the wordmark. */
export function Crimp({ width = 64, tint = color.blue }: { width?: number; tint?: string }) {
  return (
    <Svg width={width} height={(width * 34) / 88} viewBox="6 36.5 88 34">
      <Path
        d={D}
        fill="none"
        stroke={tint}
        strokeWidth={5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
