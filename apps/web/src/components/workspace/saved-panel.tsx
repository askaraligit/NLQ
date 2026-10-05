"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Play, Trash2 } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { deleteSaved, getSaved, type SavedQuery } from "@/lib/api/workspace";

export function SavedPanel() {
  const { token } = useAuth(); const [items, setItems] = useState<SavedQuery[]>([]); const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (token) getSaved(token).then(setItems).catch((e: unknown) => setError(e instanceof Error ? e.message : "Unable to load saved queries.")); }, [token]);
  async function remove(id: string) { if (!token) return; try { await deleteSaved(token, id); setItems((old) => old.filter((item) => item.id !== id)); } catch (e) { setError(e instanceof Error ? e.message : "Unable to delete query."); } }
  return <section><p className="text-xs font-semibold tracking-[0.14em] text-primary uppercase">Your workspace</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Saved queries</h1><p className="mt-2 text-sm text-muted-foreground">Keep the questions you return to most often.</p>{error ? <p role="alert" className="mt-6 text-sm text-destructive">{error}</p> : null}<div className="mt-8 grid gap-4 sm:grid-cols-2">{items.map((item) => <article key={item.id} className="rounded-xl border bg-card p-5"><h2 className="font-medium">{item.name}</h2><p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{item.question}</p><div className="mt-5 flex gap-2"><Link href={`/?question=${encodeURIComponent(item.question)}`} className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"><Play className="size-3.5" />Run</Link><button type="button" onClick={() => remove(item.id)} className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-sm hover:bg-accent"><Trash2 className="size-3.5" />Delete</button></div></article>)}{!items.length && !error ? <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground sm:col-span-2">Save a query from any result to keep it here.</p> : null}</div></section>;
}
