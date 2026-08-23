import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import * as api from "../api/client";
import type { User } from "../types";

interface AuthValue {
  user: User | null;
  ready: boolean; // false until we've checked for an existing session
  signup: (email: string, password: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthCtx = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  // Rehydrate from a stored token on load, so a refresh keeps you signed in.
  useEffect(() => {
    api
      .me()
      .then((u) => setUser(u))
      .finally(() => setReady(true));
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    const res = await api.signup(email, password);
    api.setToken(res.token);
    setUser({ email: res.email });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    api.setToken(res.token);
    setUser({ email: res.email });
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    api.setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, ready, signup, login, logout }),
    [user, ready, signup, login, logout]
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
