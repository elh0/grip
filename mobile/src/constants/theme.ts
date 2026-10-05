import tokens from './brand-tokens.json';

/**
 * grip theme. Dark to look, light to decide: video and playback sit on black,
 * lists and choices sit on white. Mat blue is only for the wordmark, the crimp and
 * the tracked body; notes, markers and buttons are black or white.
 */
export const color = {
  blue: tokens.color.matBlue,
  black: tokens.color.black,
  white: tokens.color.white,
  tile: tokens.color.tile,
  dark: {
    bg: tokens.color.black,
    text: 'rgba(243,243,240,0.95)',
    quiet: 'rgba(243,243,240,0.55)',
    rule: 'rgba(243,243,240,0.16)',
  },
  light: {
    bg: tokens.color.white,
    text: 'rgba(0,0,0,0.92)',
    quiet: 'rgba(0,0,0,0.5)',
    rule: 'rgba(0,0,0,0.12)',
  },
} as const;

export type Tone = 'dark' | 'light';

/** Regular weight only. Size makes the hierarchy; mono caps for times and labels. */
export const font = {
  sans: 'HostGrotesk_400Regular',
  mono: 'DMMono_400Regular',
} as const;

export const size = {
  label: 11,
  body: 16,
  title: 22,
  display: 30,
} as const;

export const space = (n: number) => n * 4;

export const type = {
  label: { fontFamily: font.mono, fontSize: size.label, letterSpacing: 0.6, textTransform: 'uppercase' },
  body: { fontFamily: font.sans, fontSize: size.body, lineHeight: 22 },
  title: { fontFamily: font.sans, fontSize: size.title, lineHeight: 28 },
  display: { fontFamily: font.sans, fontSize: size.display, lineHeight: 36 },
} as const;
