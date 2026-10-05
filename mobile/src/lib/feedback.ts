import type { FeedbackItem, Session, SessionStatus, Severity, Sport } from './types';

export const MAX_NOTES = 3;

/** 42.7 -> "0:42" */
export function formatTime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export const sportLabel: Record<Sport, string> = { climbing: 'Climb', bjj: 'Roll' };

const statusText: Record<SessionStatus, string> = {
  draft: 'Not uploaded',
  uploaded: 'Waiting',
  analyzing: 'Watching',
  done: 'Reviewed',
  failed: 'Failed',
};

export function statusLabel(status: SessionStatus, notes?: number): string {
  if (status === 'done' && notes !== undefined) {
    return notes === 0 ? 'No notes' : `${notes} note${notes === 1 ? '' : 's'}`;
  }
  return statusText[status];
}

export const isPending = (status: SessionStatus) => status === 'uploaded' || status === 'analyzing';

const severityRank: Record<Severity, number> = { major: 0, moderate: 1, minor: 2 };

/** Notes in clip order, never more than three. */
export function orderNotes(items: FeedbackItem[]): FeedbackItem[] {
  return [...items]
    .sort((a, b) => severityRank[a.severity] - severityRank[b.severity] || a.position - b.position)
    .slice(0, MAX_NOTES)
    .sort((a, b) => a.t_seconds - b.t_seconds);
}

export interface Marker {
  id: string;
  left: number; // 0..1 along the timeline
  severity: Severity;
}

export function timelineMarkers(items: FeedbackItem[], duration: number): Marker[] {
  if (!duration || duration <= 0) return [];
  return orderNotes(items).map((it) => ({
    id: it.id,
    left: Math.min(1, Math.max(0, it.t_seconds / duration)),
    severity: it.severity,
  }));
}

/** The note whose moment the playhead is on (within a window after it). */
export function activeNote(items: FeedbackItem[], t: number, windowS = 2.5): FeedbackItem | null {
  let best: FeedbackItem | null = null;
  for (const it of items) {
    if (t >= it.t_seconds - 0.25 && t <= it.t_seconds + windowS) {
      if (!best || it.t_seconds > best.t_seconds) best = it;
    }
  }
  return best;
}

export function sessionTitle(s: Pick<Session, 'title' | 'sport' | 'created_at'>): string {
  if (s.title?.trim()) return s.title.trim();
  const d = new Date(s.created_at);
  const day = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  return `${sportLabel[s.sport]}, ${day}`;
}
