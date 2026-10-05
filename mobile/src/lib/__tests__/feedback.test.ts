import { expect, test } from '@jest/globals';

import {
  activeNote,
  formatTime,
  isPending,
  orderNotes,
  sessionTitle,
  statusLabel,
  timelineMarkers,
} from '../feedback';
import type { FeedbackItem, Severity } from '../types';

const note = (id: string, t: number, severity: Severity = 'moderate', position = 1): FeedbackItem => ({
  id,
  session_id: 's',
  position,
  t_seconds: t,
  body_part: 'Left hip',
  severity,
  observation: 'o',
  cue: 'c',
  drill: null,
  frame_path: null,
});

test('formatTime', () => {
  expect(formatTime(0)).toBe('0:00');
  expect(formatTime(42.7)).toBe('0:42');
  expect(formatTime(125)).toBe('2:05');
  expect(formatTime(-3)).toBe('0:00');
});

test('statusLabel counts notes once reviewed', () => {
  expect(statusLabel('done', 0)).toBe('No notes');
  expect(statusLabel('done', 1)).toBe('1 note');
  expect(statusLabel('done', 3)).toBe('3 notes');
  expect(statusLabel('analyzing')).toBe('Watching');
  expect(isPending('uploaded')).toBe(true);
  expect(isPending('done')).toBe(false);
});

test('orderNotes keeps the three most severe, in clip order', () => {
  const items = [
    note('a', 9, 'minor', 1),
    note('b', 2, 'major', 2),
    note('c', 5, 'moderate', 3),
    note('d', 1, 'moderate', 4),
  ];
  expect(orderNotes(items).map((n) => n.id)).toEqual(['d', 'b', 'c']);
});

test('timelineMarkers places and clamps ticks', () => {
  const m = timelineMarkers([note('a', 5), note('b', 30)], 20);
  expect(m.map((x) => x.left)).toEqual([0.25, 1]);
  expect(timelineMarkers([note('a', 5)], 0)).toEqual([]);
});

test('activeNote follows the playhead', () => {
  const items = [note('a', 2), note('b', 4)];
  expect(activeNote(items, 0.5)).toBeNull();
  expect(activeNote(items, 2.1)?.id).toBe('a');
  expect(activeNote(items, 4.2)?.id).toBe('b');
  expect(activeNote(items, 9)).toBeNull();
});

test('sessionTitle falls back to sport and date', () => {
  expect(sessionTitle({ title: ' Moon 6B+ ', sport: 'climbing', created_at: '2026-10-05T10:00:00Z' })).toBe('Moon 6B+');
  expect(sessionTitle({ title: null, sport: 'bjj', created_at: '2026-10-05T10:00:00Z' })).toBe('Roll, 5 Oct');
});
