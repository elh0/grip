import { File } from 'expo-file-system';

import { supabase } from './supabase';
import type { Session, Sport } from './types';

export interface NewSession {
  sport: Sport;
  videoUri: string;
  note?: string;
  title?: string;
}

export function videoObjectPath(userId: string, sessionId: string, uri: string): string {
  const ext = /\.mov$/i.test(uri) ? 'mov' : 'mp4';
  return `${userId}/${sessionId}.${ext}`;
}

export const contentTypeFor = (path: string) =>
  path.endsWith('.mov') ? 'video/quicktime' : 'video/mp4';

/**
 * Create the session row, PUT the clip to a signed Storage URL with progress, then mark
 * it uploaded (which queues the analysis job in the database).
 */
export async function uploadSession(
  input: NewSession,
  onProgress: (fraction: number) => void,
): Promise<Session> {
  const { data: auth } = await supabase.auth.getUser();
  const userId = auth.user?.id;
  if (!userId) throw new Error('Sign in first.');

  const { data: created, error: createError } = await supabase
    .from('sessions')
    .insert({
      user_id: userId,
      sport: input.sport,
      athlete_note: input.note?.trim() || null,
      title: input.title?.trim() || null,
    })
    .select()
    .single<Session>();
  if (createError || !created) throw createError ?? new Error('Could not create the session.');

  const path = videoObjectPath(userId, created.id, input.videoUri);
  const { data: signed, error: signError } = await supabase.storage
    .from('videos')
    .createSignedUploadUrl(path);
  if (signError || !signed) throw signError ?? new Error('Could not start the upload.');

  const task = new File(input.videoUri).createUploadTask(signed.signedUrl, {
    httpMethod: 'PUT',
    headers: { 'Content-Type': contentTypeFor(path), 'x-upsert': 'true' },
    onProgress: ({ bytesSent, totalBytes }) => {
      if (totalBytes > 0) onProgress(bytesSent / totalBytes);
    },
  });
  const result = await task.uploadAsync();
  if (!result || result.status < 200 || result.status >= 300) {
    throw new Error(`Upload failed (${result?.status ?? 'no response'}).`);
  }

  const { data: updated, error: updateError } = await supabase
    .from('sessions')
    .update({ status: 'uploaded', video_path: path })
    .eq('id', created.id)
    .select()
    .single<Session>();
  if (updateError || !updated) throw updateError ?? new Error('Could not queue the review.');
  onProgress(1);
  return updated;
}

export async function signedUrl(bucket: 'videos' | 'frames', path: string, expiresIn = 3600) {
  const { data, error } = await supabase.storage.from(bucket).createSignedUrl(path, expiresIn);
  if (error) throw error;
  return data.signedUrl;
}

/** Delete the clip, its frames and the session (feedback cascades). */
export async function deleteSession(session: Session, framePaths: string[]): Promise<void> {
  const videos = session.video_path ? [session.video_path] : [];
  if (videos.length) await supabase.storage.from('videos').remove(videos);
  if (framePaths.length) await supabase.storage.from('frames').remove(framePaths);
  const { error } = await supabase.from('sessions').delete().eq('id', session.id);
  if (error) throw error;
}
