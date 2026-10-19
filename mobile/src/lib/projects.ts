import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';

import { placeLabel } from './climb';
import { useGyms } from './gyms';
import { currentProject } from './progress';
import { supabase } from './supabase';
import type { Gym, Project } from './types';
import { syncWidget } from './widget';

export type ProjectDraft = Partial<
  Pick<Project, 'name' | 'gym_id' | 'place' | 'wall' | 'colour' | 'grade' | 'next_note' | 'resets_on' | 'pinned' | 'status' | 'sent_at'>
>;

/** "BlocFit · Cave" in a gym, the crag outdoors, or null. */
export function projectPlace(p: Pick<Project, 'gym_id' | 'place' | 'wall'>, byId: Record<string, Gym>): string | null {
  if (p.gym_id) return placeLabel(byId[p.gym_id], p.wall);
  return [p.place?.trim(), p.wall?.trim()].filter(Boolean).join(' · ') || null;
}

/** Your projects, newest first; live, and keeps the widget in step. */
export function useProjects() {
  const { byId } = useGyms();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const { data } = await supabase.from('projects').select('*').order('updated_at', { ascending: false }).limit(100);
    setProjects((data as Project[]) ?? []);
    setLoading(false);
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  useEffect(() => {
    const channel = supabase
      .channel('projects')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'projects' }, () => load())
      .subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
  }, [load]);

  const current = currentProject(projects);
  useEffect(() => {
    if (!loading) syncWidget(current, current ? projectPlace(current, byId) : null);
  }, [current, byId, loading]);

  return { projects, current, loading, load };
}

export async function saveProject(id: string | null, draft: ProjectDraft): Promise<Project> {
  const { data: auth } = await supabase.auth.getUser();
  const userId = auth.user?.id;
  if (!userId) throw new Error('Sign in first.');
  if (draft.pinned) {
    // one pinned project at a time
    await supabase.from('projects').update({ pinned: false }).eq('user_id', userId).eq('pinned', true).neq('id', id ?? '');
  }
  const q = id
    ? supabase.from('projects').update(draft).eq('id', id)
    : supabase.from('projects').insert({ ...draft, user_id: userId });
  const { data, error } = await q.select().single<Project>();
  if (error || !data) throw error ?? new Error('Could not save the project.');
  return data;
}

/** Make a coach note your next-go note on the climb's project. */
export async function setNextNote(projectId: string, note: string) {
  const { error } = await supabase.from('projects').update({ next_note: note.slice(0, 280) }).eq('id', projectId);
  if (error) throw error;
}

export async function deleteProject(id: string) {
  const { error } = await supabase.from('projects').delete().eq('id', id);
  if (error) throw error;
}
