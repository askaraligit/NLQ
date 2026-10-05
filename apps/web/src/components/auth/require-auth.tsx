"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/auth-provider";

export function RequireAuth({ children }: Readonly<{ children: React.ReactNode }>) {
  const { isReady, token } = useAuth();
  const router = useRouter();
  useEffect(() => { if (isReady && !token) router.replace("/login"); }, [isReady, router, token]);
  if (!isReady || !token) return <div className="py-16 text-center text-sm text-muted-foreground">Loading workspace…</div>;
  return <>{children}</>;
}
