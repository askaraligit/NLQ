"use client";

import { useEffect, useState } from "react";
import { Check, LoaderCircle } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { fetchSettings, type WorkspaceSettings, updateSettings } from "@/lib/api/auth";
import { Button } from "@/components/ui/button";

const initial: WorkspaceSettings = { preferredPageSize: 25, compactTables: false };
export function SettingsPanel() {
  const { token, user } = useAuth(); const [settings, setSettings] = useState<WorkspaceSettings>(initial); const [state, setState] = useState<"idle" | "saving" | "saved">("idle"); const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (token) fetchSettings(token).then(setSettings).catch((e: unknown) => setError(e instanceof Error ? e.message : "Unable to load settings.")); }, [token]);
  async function save() { if (!token) return; setState("saving"); setError(null); try { setSettings(await updateSettings(token, settings)); setState("saved"); } catch (e) { setError(e instanceof Error ? e.message : "Unable to save settings."); setState("idle"); } }
  return <section className="max-w-xl"><p className="text-xs font-semibold tracking-[0.14em] text-primary uppercase">Your workspace</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Settings</h1><p className="mt-2 text-sm text-muted-foreground">Signed in as {user?.email}.</p><div className="mt-8 space-y-6 rounded-xl border bg-card p-6"><label className="block text-sm font-medium">Rows per result page<select value={settings.preferredPageSize} onChange={(e) => setSettings({ ...settings, preferredPageSize: Number(e.target.value) as WorkspaceSettings["preferredPageSize"] })} className="mt-2 block w-full rounded-md border bg-background px-3 py-2"><option value={10}>10</option><option value={25}>25</option><option value={50}>50</option><option value={100}>100</option></select></label><label className="flex items-center justify-between gap-4 text-sm font-medium">Compact result tables<input type="checkbox" checked={settings.compactTables} onChange={(e) => setSettings({ ...settings, compactTables: e.target.checked })} className="size-4" /></label><Button type="button" onClick={save} disabled={state === "saving"}>{state === "saving" ? <><LoaderCircle className="size-4 animate-spin" />Saving</> : state === "saved" ? <><Check className="size-4" />Saved</> : "Save settings"}</Button>{error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}</div></section>;
}
