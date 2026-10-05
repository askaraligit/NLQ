"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Clock3 } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { getHistory, type HistoryItem } from "@/lib/api/workspace";

export function HistoryPanel() {
  const { token } = useAuth(); const [items, setItems] = useState<HistoryItem[]>([]); const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (token) getHistory(token).then(setItems).catch((e: unknown) => setError(e instanceof Error ? e.message : "Unable to load history.")); }, [token]);
  return <section><p className="text-xs font-semibold tracking-[0.14em] text-primary uppercase">Your workspace</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Query history</h1><p className="mt-2 text-sm text-muted-foreground">Reopen a previous answer or continue its conversation.</p>{error ? <p role="alert" className="mt-6 text-sm text-destructive">{error}</p> : null}<div className="mt-8 space-y-3">{items.map((item) => <article key={item.id} className="rounded-xl border bg-card p-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="font-medium">{item.question}</h2><p className="mt-2 text-sm text-muted-foreground">{item.summary}</p><p className="mt-3 inline-flex items-center gap-1 text-xs text-muted-foreground"><Clock3 className="size-3" />{new Date(item.createdAt).toLocaleString()}</p></div><Link href={`/?conversation=${item.conversationId}&question=${encodeURIComponent(item.question)}`} className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent">Continue <ArrowRight className="size-4" /></Link></div></article>)}{!items.length && !error ? <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Run a query and it will appear here.</p> : null}</div></section>;
}
