import { File } from 'expo-file-system';
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { useAuth } from './auth';
import { setPhotoPath } from './climb';
import { supabase } from './supabase';
import type { Gym, SetPost } from './types';

interface GymsState {
  gyms: Gym[];
  byId: Record<string, Gym>;
  follows: Set<string>;
  toggleFollow: (gymId: string) => Promise<void>;
  reload: () => Promise<void>;
}

const GymsContext = createContext<GymsState>({
  gyms: [],
  byId: {},
  follows: new Set(),
  toggleFollow: async () => undefined,
  reload: async () => undefined,
});

/** London gyms and the ones you follow, shared by every tab. */
export function GymsProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const userId = session?.user.id;
  const [gyms, setGyms] = useState<Gym[]>([]);
  const [follows, setFollows] = useState<Set<string>>(new Set());

  const reload = useCallback(async () => {
    if (!userId) return;
    const [{ data: g }, { data: f }] = await Promise.all([
      supabase.from('gyms').select('*').order('name'),
      supabase.from('gym_follows').select('gym_id'),
    ]);
    setGyms((g as Gym[]) ?? []);
    setFollows(new Set(((f as { gym_id: string }[]) ?? []).map((r) => r.gym_id)));
  }, [userId]);

  useEffect(() => {
    // Fetch once signed in; state is only set after the await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    reload();
  }, [reload]);

  const toggleFollow = useCallback(
    async (gymId: string) => {
      if (!userId) return;
      const on = follows.has(gymId);
      const next = new Set(follows);
      if (on) next.delete(gymId);
      else next.add(gymId);
      setFollows(next); // optimistic
      const { error } = on
        ? await supabase.from('gym_follows').delete().eq('gym_id', gymId).eq('user_id', userId)
        : await supabase.from('gym_follows').insert({ user_id: userId, gym_id: gymId });
      if (error) setFollows(follows);
    },
    [follows, userId],
  );

  const value = useMemo(
    () => ({ gyms, byId: Object.fromEntries(gyms.map((g) => [g.id, g])), follows, toggleFollow, reload }),
    [gyms, follows, toggleFollow, reload],
  );
  return <GymsContext.Provider value={value}>{children}</GymsContext.Provider>;
}

export const useGyms = () => useContext(GymsContext);

export interface NewSet {
  gymId: string;
  wall?: string;
  colours: string[];
  note?: string;
  photoUri: string;
}

/** RFC 4122 v4 id made on the phone, so the photo path and the row share it. */
export function uuid(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/** Upload the photo to the `sets` bucket, then create the post (followers get an alert). */
export async function postSet(input: NewSet): Promise<SetPost> {
  const { data: auth } = await supabase.auth.getUser();
  const userId = auth.user?.id;
  if (!userId) throw new Error('Sign in first.');
  const id = uuid();
  const path = setPhotoPath(userId, id, input.photoUri);
  const bytes = await new File(input.photoUri).arrayBuffer();
  const type = path.endsWith('.png') ? 'image/png' : path.endsWith('.heic') ? 'image/heic' : 'image/jpeg';
  const { error: upErr } = await supabase.storage.from('sets').upload(path, bytes, { contentType: type });
  if (upErr) throw upErr;
  const { data, error } = await supabase
    .from('set_posts')
    .insert({
      id,
      user_id: userId,
      gym_id: input.gymId,
      wall: input.wall?.trim() || null,
      colours: input.colours,
      note: input.note?.trim() || null,
      photo_path: path,
    })
    .select()
    .single<SetPost>();
  if (error || !data) throw error ?? new Error('Could not post the set.');
  return data;
}

export async function deleteSet(post: SetPost): Promise<void> {
  await supabase.storage.from('sets').remove([post.photo_path]);
  const { error } = await supabase.from('set_posts').delete().eq('id', post.id);
  if (error) throw error;
}

export async function setPhotoUrls(paths: string[]): Promise<Record<string, string>> {
  if (!paths.length) return {};
  const { data } = await supabase.storage.from('sets').createSignedUrls(paths, 3600);
  return Object.fromEntries((data ?? []).flatMap((d) => (d.signedUrl && d.path ? [[d.path, d.signedUrl] as const] : [])));
}

export async function requestGym(name: string, area: string): Promise<void> {
  const { data: auth } = await supabase.auth.getUser();
  const userId = auth.user?.id;
  if (!userId) throw new Error('Sign in first.');
  const { error } = await supabase
    .from('gym_requests')
    .insert({ user_id: userId, name: name.trim(), area: area.trim() || null });
  if (error) throw error;
}
