import { Text as RNText, type TextProps } from 'react-native';

import { color, type Tone, type as typo } from '@/constants/theme';

type Variant = keyof typeof typo;

export function Text({
  variant = 'body',
  tone = 'light',
  quiet = false,
  style,
  ...rest
}: TextProps & { variant?: Variant; tone?: Tone; quiet?: boolean }) {
  const palette = color[tone];
  return (
    <RNText
      style={[typo[variant], { color: quiet ? palette.quiet : palette.text }, style]}
      {...rest}
    />
  );
}
