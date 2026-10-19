import { Platform } from 'react-native';

import { projectTitle } from './progress';
import type { Project } from './types';

/**
 * Push the current project to the iOS home and lock screen widget. Quietly does nothing
 * where widgets don't exist (Android, web, Expo Go, tests).
 */
export function syncWidget(project: Project | null, place: string | null) {
  if (Platform.OS !== 'ios') return;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- loaded lazily so the widget module only loads on iOS
    const { yourProjectWidget } = require('@/widgets/your-project') as typeof import('@/widgets/your-project');
    yourProjectWidget.updateSnapshot({
      id: project?.id ?? null,
      title: project ? projectTitle(project) : 'Pick a project',
      place,
      grade: project?.grade ?? null,
      note: project?.next_note ?? null,
      resetsOn: project?.resets_on ?? null,
    });
  } catch {
    // no widget extension in this build
  }
}
