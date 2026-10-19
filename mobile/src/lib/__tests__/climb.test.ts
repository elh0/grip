import { expect, test } from '@jest/globals';

import { colourHex, filterSets, placeLabel, resultLabel, setPhotoPath, sortGyms, timeAgo } from '../climb';

const gyms = [
  { id: 'yonder', name: 'Yonder', area: 'Walthamstow' },
  { id: 'blocfit', name: 'BlocFit', area: 'Brixton' },
  { id: 'arch-b1', name: 'The Arch, Building One', area: 'Bermondsey' },
];

test('followed gyms come first, then A to Z, and search matches the area', () => {
  expect(sortGyms(gyms, new Set(['yonder'])).map((g) => g.id)).toEqual(['yonder', 'blocfit', 'arch-b1']);
  expect(sortGyms(gyms, new Set(), 'brix').map((g) => g.id)).toEqual(['blocfit']);
});

test('the following filter keeps only followed gyms, newest first', () => {
  const posts = [
    { id: 'a', gym_id: 'yonder', created_at: '2026-10-18T10:00:00Z' },
    { id: 'b', gym_id: 'blocfit', created_at: '2026-10-19T10:00:00Z' },
    { id: 'c', gym_id: 'blocfit', created_at: '2026-10-17T10:00:00Z' },
  ];
  expect(filterSets(posts, new Set(['blocfit']), 'following').map((p) => p.id)).toEqual(['b', 'c']);
  expect(filterSets(posts, new Set(), 'all').map((p) => p.id)).toEqual(['b', 'a', 'c']);
});

test('labels', () => {
  expect(placeLabel({ name: 'BlocFit' }, 'Cave')).toBe('BlocFit · Cave');
  expect(placeLabel({ name: 'BlocFit' }, '  ')).toBe('BlocFit');
  expect(placeLabel(undefined, null)).toBeNull();
  expect(resultLabel('flash')).toBe('Flash');
  expect(colourHex('purple')).toBe('#8A5BD6');
  expect(colourHex('teal')).toBe('#555555');
});

test('time ago', () => {
  const now = new Date('2026-10-19T12:00:00Z').getTime();
  expect(timeAgo('2026-10-19T11:59:40Z', now)).toBe('just now');
  expect(timeAgo('2026-10-19T11:48:00Z', now)).toBe('12 min ago');
  expect(timeAgo('2026-10-19T09:00:00Z', now)).toBe('3h ago');
  expect(timeAgo('2026-10-18T10:00:00Z', now)).toBe('yesterday');
});

test('set photos live under the poster folder', () => {
  expect(setPhotoPath('u1', 'p1', 'file:///x/IMG_1.HEIC')).toBe('u1/p1.heic');
  expect(setPhotoPath('u1', 'p1', 'file:///x/a.jpeg')).toBe('u1/p1.jpg');
});
