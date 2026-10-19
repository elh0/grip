import { supabase } from './supabase';
import type { NoteRating } from './types';

export async function loadRatings(itemIds: string[]): Promise<Record<string, NoteRating>> {
  if (!itemIds.length) return {};
  const { data } = await supabase.from('note_ratings').select('*').in('feedback_item_id', itemIds);
  return Object.fromEntries(((data as NoteRating[]) ?? []).map((r) => [r.feedback_item_id, r]));
}

/** Thumbs up or down on a note, with an optional reason. */
export async function rateNote(itemId: string, vote: 'up' | 'down', why?: string): Promise<void> {
  const { data: auth } = await supabase.auth.getUser();
  const userId = auth.user?.id;
  if (!userId) throw new Error('Sign in first.');
  const { error } = await supabase.from('note_ratings').upsert({
    feedback_item_id: itemId,
    user_id: userId,
    vote,
    why: why?.trim() || null,
  });
  if (error) throw error;
}

export async function clearRating(itemId: string): Promise<void> {
  const { error } = await supabase.from('note_ratings').delete().eq('feedback_item_id', itemId);
  if (error) throw error;
}
