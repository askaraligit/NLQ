"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { login as requestLogin, type SessionUser } from "@/lib/api/auth";

type StoredSession = { token: string; user: SessionUser };
type AuthContextValue = {
  isReady: boolean;
  token: string | null;
  user: SessionUser | null;
  login(email: string, password: string): Promise<void>;
  logout(): void;
};

const storageKey = "nlq.session";
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [session, setSession] = useState<StoredSession | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    try {
      const stored = window.sessionStorage.getItem(storageKey);
      if (stored) {
        const parsed: unknown = JSON.parse(stored);
        if (typeof parsed === "object" && parsed !== null && "token" in parsed && "user" in parsed && typeof parsed.token === "string") {
          setSession(parsed as StoredSession);
        }
      }
    } finally {
      setIsReady(true);
    }
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    isReady,
    token: session?.token ?? null,
    user: session?.user ?? null,
    async login(email, password) {
      const response = await requestLogin(email, password);
      const next = { token: response.accessToken, user: response.user };
      window.sessionStorage.setItem(storageKey, JSON.stringify(next));
      setSession(next);
    },
    logout() {
      window.sessionStorage.removeItem(storageKey);
      setSession(null);
    },
  }), [isReady, session]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}
