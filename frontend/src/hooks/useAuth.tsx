import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import type { User } from '../types';
import { authApi } from '../services/api';

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const restore = async () => {
      // Optimistically restore the cached profile, then revalidate the
      // cookie-backed session against the server.
      let stored: User | null = null;
      try {
        const raw = localStorage.getItem('cloudforge_user');
        stored = raw ? (JSON.parse(raw) as User) : null;
      } catch {
        localStorage.removeItem('cloudforge_user');
      }
      if (stored && !cancelled) setUser(stored);

      try {
        // On 401 the api interceptor refreshes once and retries automatically.
        const res = await authApi.me();
        if (!cancelled) {
          setUser(res.data);
          localStorage.setItem('cloudforge_user', JSON.stringify(res.data));
        }
      } catch {
        // Session revalidation failed: either a 401 (already handled globally —
        // refresh attempted, then signed out) or a network problem, in which
        // case we keep the cached profile rather than logging the user out.
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = async (email: string, password: string) => {
    const res = await authApi.login({ email, password });
    const { user: userData } = res.data;
    // Access token stored in httpOnly cookie by the server.
    setUser(userData);
    localStorage.setItem('cloudforge_user', JSON.stringify(userData));
  };

  const register = async (email: string, username: string, password: string) => {
    const res = await authApi.register({ email, username, password });
    const { user: userData } = res.data;
    setUser(userData);
    localStorage.setItem('cloudforge_user', JSON.stringify(userData));
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('cloudforge_user');
    authApi.logout();
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
