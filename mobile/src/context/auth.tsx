import type { Session } from '@supabase/supabase-js';
import { createContext, type PropsWithChildren, useContext, useEffect, useState } from 'react';

import { supabase } from '@/lib/supabase';

type AuthContextValue = {
  session: Session | null;
  isLoading: boolean;
  signIn: (identifier: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function identifierToEmail(identifier: string): string {
  const normalized = identifier.trim().toLowerCase();
  return normalized.includes('@') ? normalized : `${normalized}@plantalk.local`;
}

function loginErrorMessage(message: string): string {
  if (message.toLowerCase().includes('invalid login credentials')) {
    return '아이디 또는 비밀번호가 올바르지 않습니다.';
  }
  return '로그인하지 못했습니다. 잠시 후 다시 시도해 주세요.';
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (mounted) {
        setSession(data.session);
        setIsLoading(false);
      }
    });
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIsLoading(false);
    });
    return () => {
      mounted = false;
      data.subscription.unsubscribe();
    };
  }, []);

  async function signIn(identifier: string, password: string) {
    const email = identifierToEmail(identifier);
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw new Error(loginErrorMessage(error.message));
    if (!data.user) throw new Error('사용자 정보를 불러오지 못했습니다.');

    const nickname = identifier.trim().split('@')[0];
    const { error: profileError } = await supabase.from('profiles').upsert({
      user_id: data.user.id,
      nickname,
    });
    if (profileError) {
      await supabase.auth.signOut();
      throw new Error('사용자 프로필을 준비하지 못했습니다. 다시 시도해 주세요.');
    }
  }

  async function signOut() {
    const { error } = await supabase.auth.signOut();
    if (error) throw new Error('로그아웃하지 못했습니다. 다시 시도해 주세요.');
  }

  return (
    <AuthContext.Provider value={{ session, isLoading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth는 AuthProvider 안에서 사용해야 합니다.');
  return context;
}
