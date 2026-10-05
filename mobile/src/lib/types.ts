export type Sport = 'climbing' | 'bjj';
export type SessionStatus = 'draft' | 'uploaded' | 'analyzing' | 'done' | 'failed';
export type Severity = 'minor' | 'moderate' | 'major';

export interface Session {
  id: string;
  user_id: string;
  sport: Sport;
  status: SessionStatus;
  title: string | null;
  athlete_note: string | null;
  video_path: string | null;
  duration_s: number | null;
  summary: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeedbackItem {
  id: string;
  session_id: string;
  position: number;
  t_seconds: number;
  body_part: string;
  severity: Severity;
  observation: string;
  cue: string;
  drill: string | null;
  frame_path: string | null;
}

export interface Profile {
  id: string;
  display_name: string | null;
  level: 'new' | 'intermediate' | 'advanced' | 'elite' | null;
  goals: string | null;
  injuries: string | null;
  push_token: string | null;
}
