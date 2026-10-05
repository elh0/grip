import type { Session as AuthSession } from '@supabase/supabase-js';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

import { registerForPush } from './push';
import { supabase } from './supabase';

interface AuthState {
  session: AuthSession | null;
  ready: boolean;
}

const AuthContext = createContext<AuthState>({ session: null, ready: false });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ session: null, ready: false });

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setState({ session: data.session, ready: true }));
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setState({ session, ready: true });
    });
    return () => data.subscription.unsubscribe();
  }, []);

  const userId = state.session?.user.id;
  useEffect(() => {
    if (userId) registerForPush(userId).catch(() => undefined);
  }, [userId]);

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
