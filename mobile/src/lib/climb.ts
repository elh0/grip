import type { ClimbResult, Gym, SetPost } from './types';

/** Hold colours most London gyms circuit by. */
export const COLOURS = [
  { id: 'black', hex: '#111111' },
  { id: 'white', hex: '#F3F3F0' },
  { id: 'grey', hex: '#8A8A8A' },
  { id: 'red', hex: '#E0443E' },
  { id: 'orange', hex: '#F08A24' },
  { id: 'yellow', hex: '#F2D43C' },
  { id: 'green', hex: '#3FAE5A' },
  { id: 'blue', hex: '#3D7EE8' },
  { id: 'purple', hex: '#8A5BD6' },
  { id: 'pink', hex: '#EE7FB7' },
] as const;

export const GRADES = ['V0', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6', 'V7', 'V8+'] as const;

export const RESULTS: { id: ClimbResult; label: string }[] = [
  { id: 'flash', label: 'Flash' },
  { id: 'sent', label: 'Sent' },
  { id: 'fell', label: 'Fell' },
];

export const colourHex = (id: string | null | undefined) =>
  COLOURS.find((c) => c.id === id)?.hex ?? '#555555';

export const resultLabel = (r: ClimbResult | null | undefined) =>
  RESULTS.find((x) => x.id === r)?.label ?? '';

/** "BlocFit · Cave", or the gym alone, or null when untagged. */
export function placeLabel(gym: Pick<Gym, 'name'> | undefined, wall?: string | null): string | null {
  if (!gym) return wall?.trim() || null;
  return wall?.trim() ? `${gym.name} · ${wall.trim()}` : gym.name;
}

export function gymLabel(g: Pick<Gym, 'name' | 'area'>): string {
  return g.area ? `${g.name} · ${g.area}` : g.name;
}

/** Followed gyms first, then A to Z; optional search on name or area. */
export function sortGyms<T extends Pick<Gym, 'id' | 'name' | 'area'>>(
  gyms: T[],
  follows: Set<string>,
  query = '',
): T[] {
  const q = query.trim().toLowerCase();
  return gyms
    .filter((g) => !q || `${g.name} ${g.area ?? ''}`.toLowerCase().includes(q))
    .sort(
      (a, b) =>
        Number(follows.has(b.id)) - Number(follows.has(a.id)) ||
        a.name.localeCompare(b.name) ||
        (a.area ?? '').localeCompare(b.area ?? ''),
    );
}

export type SetsFilter = 'following' | 'all';

/** Newest first; "following" keeps only gyms you follow. */
export function filterSets<T extends Pick<SetPost, 'gym_id' | 'created_at'>>(
  posts: T[],
  follows: Set<string>,
  filter: SetsFilter,
): T[] {
  return posts
    .filter((p) => filter === 'all' || follows.has(p.gym_id))
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
}

/** "just now", "12 min ago", "3h ago", "yesterday", "4 days ago". */
export function timeAgo(iso: string, now = Date.now()): string {
  const m = Math.round((now - new Date(iso).getTime()) / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return d === 1 ? 'yesterday' : `${d} days ago`;
}

export function setPhotoPath(userId: string, postId: string, uri: string): string {
  const ext = /\.png$/i.test(uri) ? 'png' : /\.heic$/i.test(uri) ? 'heic' : 'jpg';
  return `${userId}/${postId}.${ext}`;
}
