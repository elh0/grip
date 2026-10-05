import { expect, jest, test } from '@jest/globals';

import { contentTypeFor, videoObjectPath } from '../upload';

// jest hoists these above the import
jest.mock('../supabase', () => ({ supabase: {} }));
jest.mock('expo-file-system', () => ({ File: jest.fn() }));

test('clips live under the user folder, keyed by session', () => {
  expect(videoObjectPath('u1', 's1', 'file:///tmp/clip.MOV')).toBe('u1/s1.mov');
  expect(videoObjectPath('u1', 's1', 'file:///tmp/clip.mp4')).toBe('u1/s1.mp4');
  expect(videoObjectPath('u1', 's1', 'content://media/123')).toBe('u1/s1.mp4');
});

test('content type matches the extension', () => {
  expect(contentTypeFor('u1/s1.mov')).toBe('video/quicktime');
  expect(contentTypeFor('u1/s1.mp4')).toBe('video/mp4');
});
