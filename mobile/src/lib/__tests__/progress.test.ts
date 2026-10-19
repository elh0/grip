import { describe, expect, it } from '@jest/globals';

import { allowanceLabel, currentProject, daysFromNow, gradePyramid, isLimitError, projectTitle, resetLabel } from '../progress';

const s = (id: string, grade: string | null, result: 'flash' | 'sent' | 'fell' | null, project_id: string | null = null) => ({
  id,
  grade,
  result,
  project_id,
});

describe('gradePyramid', () => {
  it('counts each climb once, hardest first, flash beats send', () => {
    const rows = gradePyramid([
      s('1', 'V3', 'sent'),
      s('2', 'V5', 'fell', 'p1'),
      s('3', 'V5', 'sent', 'p1'),
      s('4', 'V5', 'sent', 'p1'),
      s('5', 'V3', 'flash'),
      s('6', 'V4', 'fell'),
      s('7', null, 'sent'),
    ]);
    expect(rows).toEqual([
      { grade: 'V5', sends: 1, flashes: 0 },
      { grade: 'V3', sends: 2, flashes: 1 },
    ]);
  });
});

describe('currentProject', () => {
  const p = (id: string, status: 'open' | 'sent', pinned: boolean, updated_at: string) => ({ id, status, pinned, updated_at });
  it('prefers the pinned open project', () => {
    expect(currentProject([p('a', 'open', false, '2026-10-19'), p('b', 'open', true, '2026-10-01')])?.id).toBe('b');
  });
  it('falls back to the latest open project and skips sent ones', () => {
    expect(currentProject([p('a', 'open', false, '2026-10-02'), p('b', 'sent', false, '2026-10-19'), p('c', 'open', false, '2026-10-05')])?.id).toBe('c');
    expect(currentProject([p('b', 'sent', true, '2026-10-19')])).toBeNull();
  });
});

describe('resetLabel', () => {
  const now = new Date(2026, 9, 19, 15);
  it('counts days to the reset', () => {
    expect(resetLabel('2026-10-28', now)).toBe('Resets in 9 days');
    expect(resetLabel('2026-10-20', now)).toBe('Resets tomorrow');
    expect(resetLabel('2026-10-19', now)).toBe('Resets today');
    expect(resetLabel('2026-10-18', now)).toBe('Reset');
    expect(resetLabel(null, now)).toBeNull();
  });
  it('round-trips with daysFromNow', () => {
    expect(resetLabel(daysFromNow(14, now), now)).toBe('Resets in 14 days');
  });
});

describe('labels', () => {
  it('names a project', () => {
    expect(projectTitle({ name: ' Cave purple ', colour: null, grade: null })).toBe('Cave purple');
    expect(projectTitle({ name: null, colour: 'purple', grade: 'V5' })).toBe('purple V5');
    expect(projectTitle({ name: '', colour: null, grade: null })).toBe('Your project');
  });
  it('describes the allowance', () => {
    expect(allowanceLabel({ used: 1, allowed: 3, has_grip: false, resets_on: '' })).toBe('2 of 3 free reviews left this month');
    expect(allowanceLabel({ used: 3, allowed: 3, has_grip: false, resets_on: '' })).toBe('No free reviews left this month');
    expect(allowanceLabel({ used: 4, allowed: 20, has_grip: true, resets_on: '' })).toBe('16 of 20 reviews left this month');
  });
  it('spots the limit error from the database', () => {
    expect(isLimitError({ message: 'review limit reached' })).toBe(true);
    expect(isLimitError(new Error('Upload failed (500).'))).toBe(false);
  });
});
