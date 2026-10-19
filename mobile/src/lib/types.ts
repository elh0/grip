export type Sport = 'climbing' | 'bjj';
export type SessionStatus = 'draft' | 'uploaded' | 'analyzing' | 'done' | 'failed';
export type Severity = 'minor' | 'moderate' | 'major';
export type ClimbResult = 'flash' | 'sent' | 'fell';

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
  gym_id: string | null;
  wall: string | null;
  colour: string | null;
  grade: string | null;
  result: ClimbResult | null;
  project_id: string | null;
  share_path: string | null;
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

export interface Gym {
  id: string;
  name: string;
  area: string | null;
  city: string;
  website: string | null;
  instagram: string | null;
}

export interface SetPost {
  id: string;
  user_id: string;
  gym_id: string;
  wall: string | null;
  colours: string[];
  note: string | null;
  photo_path: string;
  created_at: string;
}

export interface NoteRating {
  feedback_item_id: string;
  user_id: string;
  vote: 'up' | 'down';
  why: string | null;
}

export type ProjectStatus = 'open' | 'sent' | 'dropped';

export interface Project {
  id: string;
  user_id: string;
  name: string | null;
  gym_id: string | null;
  place: string | null;
  wall: string | null;
  colour: string | null;
  grade: string | null;
  status: ProjectStatus;
  pinned: boolean;
  next_note: string | null;
  resets_on: string | null;
  sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewAllowance {
  used: number;
  allowed: number;
  has_grip: boolean;
  resets_on: string;
}
