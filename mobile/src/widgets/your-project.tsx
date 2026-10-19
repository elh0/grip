import { HStack, Spacer, Text, VStack } from '@expo/ui/swift-ui';
import { containerBackground, font, foregroundStyle, lineLimit, padding, widgetURL } from '@expo/ui/swift-ui/modifiers';
import { createWidget, type WidgetEnvironment } from 'expo-widgets';

/** What the app hands the widget; plain strings so it renders without the app running. */
export interface YourProjectProps {
  id: string | null;
  title: string;
  place: string | null;
  grade: string | null;
  note: string | null;
  resetsOn: string | null; // YYYY-MM-DD
}

// Widgets run outside React Native, so the colours are repeated from the theme here.
const BG = '#000000';
const TEXT = '#F3F3F0';
const QUIET = '#8A8A83';

function resetLine(resetsOn: string | null, now: Date): string | null {
  if (!resetsOn) return null;
  const [y, m, d] = resetsOn.split('-').map(Number);
  const days = Math.round((Date.UTC(y, m - 1, d) - Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())) / 86400000);
  if (days < 0) return 'Reset';
  if (days === 0) return 'Resets today';
  if (days === 1) return 'Resets tomorrow';
  return `Resets in ${days} days`;
}

/** Your project: the boulder you're on, your note for the next go, and when the wall resets. */
const YourProject = (p: YourProjectProps, env: WidgetEnvironment) => {
  'widget';
  const reset = resetLine(p.resetsOn, env.date);
  const label = (s: string) => (
    <Text modifiers={[font({ design: 'monospaced', size: 10 }), foregroundStyle(QUIET)]}>{s.toUpperCase()}</Text>
  );
  const url = widgetURL(p.id ? `grip://project/${p.id}` : 'grip://you');

  if (env.widgetFamily === 'accessoryRectangular' || env.widgetFamily === 'accessoryInline') {
    return (
      <VStack alignment="leading" spacing={1} modifiers={[url]}>
        <Text modifiers={[font({ size: 14 }), lineLimit(1)]}>{p.id ? p.title : 'No project yet'}</Text>
        {p.note ? <Text modifiers={[font({ size: 12 }), lineLimit(2)]}>{p.note}</Text> : null}
        {reset ? <Text modifiers={[font({ design: 'monospaced', size: 10 })]}>{reset}</Text> : null}
      </VStack>
    );
  }

  const small = env.widgetFamily === 'systemSmall';
  return (
    <VStack alignment="leading" spacing={4} modifiers={[containerBackground(BG, 'widget'), padding({ all: 2 }), url]}>
      <HStack>
        {label('Your project')}
        <Spacer />
        {p.grade ? label(p.grade) : null}
      </HStack>
      <Text modifiers={[font({ size: small ? 17 : 19 }), foregroundStyle(TEXT), lineLimit(1)]}>
        {p.id ? p.title : 'Pick a project'}
      </Text>
      {p.place ? (
        <Text modifiers={[font({ size: 12 }), foregroundStyle(QUIET), lineLimit(1)]}>{p.place}</Text>
      ) : null}
      <Spacer />
      {p.note ? (
        <VStack alignment="leading" spacing={2}>
          {label('Next go')}
          <Text modifiers={[font({ size: small ? 13 : 14 }), foregroundStyle(TEXT), lineLimit(small ? 3 : 2)]}>{p.note}</Text>
        </VStack>
      ) : p.id ? null : (
        <Text modifiers={[font({ size: 13 }), foregroundStyle(QUIET), lineLimit(3)]}>
          Start one in grip and your next-go note lands here.
        </Text>
      )}
      {reset ? label(reset) : null}
    </VStack>
  );
};

export const yourProjectWidget = createWidget<YourProjectProps>('YourProject', YourProject);
