"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LoaderCircle, Sparkles } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";

export function LoginForm() {
  const { isReady, token, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  useEffect(() => { if (isReady && token) router.replace("/"); }, [isReady, router, token]);
  async function submit(event: FormEvent) {
    event.preventDefault(); setPending(true); setError(null);
    try { await login(email, password); router.replace("/"); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to sign in."); }
    finally { setPending(false); }
  }
  return <main className="grid min-h-dvh place-items-center bg-secondary/25 px-5 py-10">
    <form onSubmit={submit} className="w-full max-w-md rounded-2xl border bg-card p-7 shadow-sm sm:p-9">
      <span className="grid size-11 place-items-center rounded-xl bg-primary text-primary-foreground"><Sparkles className="size-5" /></span>
      <h1 className="mt-6 text-2xl font-semibold tracking-tight">Sign in to NLQ</h1>
      <p className="mt-2 text-sm text-muted-foreground">Use the workspace account created by your administrator.</p>
      <label className="mt-7 block text-sm font-medium">Email<input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-2 w-full rounded-lg border bg-background px-3 py-2.5 outline-none focus:ring-2 focus:ring-ring" /></label>
      <label className="mt-4 block text-sm font-medium">Password<input required type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-2 w-full rounded-lg border bg-background px-3 py-2.5 outline-none focus:ring-2 focus:ring-ring" /></label>
      {error ? <p role="alert" className="mt-4 text-sm text-destructive">{error}</p> : null}
      <Button type="submit" className="mt-6 w-full" disabled={pending}>{pending ? <><LoaderCircle className="size-4 animate-spin" /> Signing in</> : "Sign in"}</Button>
    </form>
  </main>;
}
