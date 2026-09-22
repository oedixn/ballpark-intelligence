import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import type { AuthUser } from '../api/authApi';
import {
  clearToken,
  fetchMe,
  hasToken,
  login as loginRequest,
  register as registerRequest,
  storeToken,
} from '../api/authApi';

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!hasToken()) {
      setLoading(false);
      return;
    }
    fetchMe()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const result = await loginRequest(email, password);
    storeToken(result.access_token);
    setUser(result.user);
  }

  async function register(email: string, password: string, displayName: string) {
    const result = await registerRequest(email, password, displayName);
    storeToken(result.access_token);
    setUser(result.user);
  }

  function logout() {
    clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated: Boolean(user), login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
