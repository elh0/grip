import { GRADES } from './climb';
import type { Project, ReviewAllowance, Session } from './types';

export interface PyramidRow {
  grade: string;
  sends: number;
  flashes: number;
}

/**
 * Sends per grade, hardest first. A climb counts once: sessions on the same project are one
 * climb, and a flash beats a send. Grades with no sends are left out.
 */
export function gradePyramid(sessions: Pick<Session, 'id' | 'grade' | 'result' | 'project_id'>[]): PyramidRow[] {
  const best = new Map<string, { grade: string; flash: boolean }>();
  for (const s of sessions) {
    if (!s.grade || (s.result !== 'sent' && s.result !== 'flash')) continue;
    const key = s.project_id ?? s.id;
    const prev = best.get(key);
    best.set(key, { grade: s.grade, flash: (prev?.flash ?? false) || s.result === 'flash' });
  }
  const rows = new Map<string, PyramidRow>();
  for (const { grade, flash } of best.values()) {
    const r = rows.get(grade) ?? { grade, sends: 0, flashes: 0 };
    r.sends += 1;
    if (flash) r.flashes += 1;
    rows.set(grade, r);
  }
  const order = (g: string) => {
    const i = (GRADES as readonly string[]).indexOf(g);
    return i === -1 ? -1 : i;
  };
  return [...rows.values()].sort((a, b) => order(b.grade) - order(a.grade));
}

/** The project the widget shows: the pinned one, else the open one touched last. */
export function currentProject<T extends Pick<Project, 'status' | 'pinned' | 'updated_at'>>(projects: T[]): T | null {
  const open = projects.filter((p) => p.status === 'open');
  return open.find((p) => p.pinned) ?? [...open].sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0] ?? null;
}

/** "Resets in 9 days", "Resets tomorrow", "Resets today", "Reset", or null when unknown. */
export function resetLabel(resetsOn: string | null | undefined, now = new Date()): string | null {
  if (!resetsOn) return null;
  const [y, m, d] = resetsOn.split('-').map(Number);
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((Date.UTC(y, m - 1, d) - today) / 86400000);
  if (days < 0) return 'Reset';
  if (days === 0) return 'Resets today';
  if (days === 1) return 'Resets tomorrow';
  return `Resets in ${days} days`;
}

/** A date `days` from now as YYYY-MM-DD in local time. */
export function daysFromNow(days: number, now = new Date()): string {
  const t = new Date(now.getFullYear(), now.getMonth(), now.getDate() + days);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())}`;
}

/** "Cave purple", or the colour and grade, or "Your project". */
export function projectTitle(p: Pick<Project, 'name' | 'colour' | 'grade'>): string {
  if (p.name?.trim()) return p.name.trim();
  const bits = [p.colour, p.grade].filter(Boolean);
  return bits.length ? bits.join(' ') : 'Your project';
}

/** "2 of 3 free reviews left this month" style line for the record screen and plans. */
export function allowanceLabel(a: ReviewAllowance | null): string | null {
  if (!a) return null;
  const left = Math.max(0, a.allowed - a.used);
  if (a.has_grip) return `${left} of ${a.allowed} reviews left this month`;
  return left === 0 ? 'No free reviews left this month' : `${left} of ${a.allowed} free reviews left this month`;
}

export const isLimitError = (e: unknown) =>
  !!e && typeof e === 'object' && 'message' in e && /review limit/i.test(String((e as { message: unknown }).message));
