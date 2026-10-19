import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';

import { setPhotoUrls } from './gyms';
import { supabase } from './supabase';
import type { SetPost } from './types';

/** Latest set posts (optionally for one gym) with signed photo links; live on new posts. */
export function useSets(gymId?: string) {
  const [posts, setPosts] = useState<SetPost[]>([]);
  const [photos, setPhotos] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    let q = supabase.from('set_posts').select('*').order('created_at', { ascending: false }).limit(100);
    if (gymId) q = q.eq('gym_id', gymId);
    const { data } = await q;
    const rows = (data as SetPost[]) ?? [];
    setPosts(rows);
    setPhotos(await setPhotoUrls(rows.map((p) => p.photo_path)).catch(() => ({})));
    setLoading(false);
  }, [gymId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  useEffect(() => {
    const channel = supabase
      .channel(`sets:${gymId ?? 'all'}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'set_posts', ...(gymId ? { filter: `gym_id=eq.${gymId}` } : {}) },
        () => load(),
      )
      .subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
  }, [gymId, load]);

  return { posts, photos, loading, load };
}
