"use client";

import { FormEvent, useEffect, useState } from "react";
import { CheckCircle2, Database, LoaderCircle, Play, Trash2 } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { activateConnection, createConnection, deleteConnection, getConnections, type DataConnection, type SourceType } from "@/lib/api/connections";

export function ConnectionsPanel() {
  const { token } = useAuth();
  const [connections, setConnections] = useState<DataConnection[]>([]);
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState<SourceType>("postgresql");
  const [connectionUrl, setConnectionUrl] = useState("");
  const [schemaName, setSchemaName] = useState("public");
  const [databaseName, setDatabaseName] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (token) getConnections(token).then(setConnections).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Unable to load connections."));
  }, [token]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!token || pending) return;
    setPending(true); setError(null);
    try {
      const record = await createConnection(token, { name, sourceType, connectionUrl, schemaName, databaseName: sourceType === "mongodb" ? databaseName : undefined });
      setConnections((old) => [record, ...old.map((item) => ({ ...item, isActive: false }))]);
      setName(""); setConnectionUrl(""); setDatabaseName("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to add connection."); }
    finally { setPending(false); }
  }
  async function activate(id: string) {
    if (!token) return;
    try { const record = await activateConnection(token, id); setConnections((old) => old.map((item) => ({ ...item, isActive: item.id === record.id }))); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to activate connection."); }
  }
  async function remove(id: string) {
    if (!token) return;
    try { await deleteConnection(token, id); setConnections((old) => old.filter((item) => item.id !== id)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to delete connection."); }
  }
  const isMongo = sourceType === "mongodb";
  return <section className="max-w-3xl">
    <p className="text-xs font-semibold tracking-[0.14em] text-primary uppercase">Data sources</p>
    <h1 className="mt-2 text-3xl font-semibold tracking-tight">Connect a database</h1>
    <p className="mt-2 text-sm leading-6 text-muted-foreground">Use a dedicated read-only PostgreSQL or MongoDB account. The URL is encrypted on the API server and never returned to the browser.</p>
    <form onSubmit={submit} className="mt-8 grid gap-4 rounded-xl border bg-card p-6">
      <label className="text-sm font-medium">Connection name<input required value={name} onChange={(event) => setName(event.target.value)} placeholder="Production reporting" className="mt-2 w-full rounded-md border bg-background px-3 py-2" /></label>
      <label className="text-sm font-medium">Database type<select value={sourceType} onChange={(event) => setSourceType(event.target.value as SourceType)} className="mt-2 w-full rounded-md border bg-background px-3 py-2"><option value="postgresql">PostgreSQL</option><option value="mongodb">MongoDB</option></select></label>
      <label className="text-sm font-medium">{isMongo ? "MongoDB connection URI" : "PostgreSQL connection URL"}<input required type="password" value={connectionUrl} onChange={(event) => setConnectionUrl(event.target.value)} placeholder={isMongo ? "mongodb+srv://reader:password@cluster.example.net" : "postgresql://reader:password@host:5432/database"} className="mt-2 w-full rounded-md border bg-background px-3 py-2" /></label>
      {isMongo ? <label className="text-sm font-medium">MongoDB database<input required value={databaseName} onChange={(event) => setDatabaseName(event.target.value)} placeholder="reporting" className="mt-2 w-full rounded-md border bg-background px-3 py-2" /></label> : <label className="text-sm font-medium">Schema<input required value={schemaName} onChange={(event) => setSchemaName(event.target.value)} className="mt-2 w-full rounded-md border bg-background px-3 py-2" /></label>}
      <Button type="submit" disabled={pending}>{pending ? <><LoaderCircle className="size-4 animate-spin" />Testing connection</> : <><Database className="size-4" />Test and connect</>}</Button>
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </form>
    <div className="mt-8 space-y-3">{connections.map((connection) => <article key={connection.id} className="flex flex-wrap items-center justify-between gap-4 rounded-xl border bg-card p-5"><div><div className="flex items-center gap-2"><h2 className="font-medium">{connection.name}</h2>{connection.isActive ? <span className="inline-flex items-center gap-1 text-xs text-primary"><CheckCircle2 className="size-3.5" />Active</span> : null}</div><p className="mt-1 text-sm text-muted-foreground">{connection.sourceType === "mongodb" ? "MongoDB: " + connection.databaseName : "PostgreSQL schema: " + connection.schemaName}</p></div><div className="flex gap-2">{!connection.isActive ? <button type="button" onClick={() => activate(connection.id)} className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-sm hover:bg-accent"><Play className="size-3.5" />Use</button> : null}<button type="button" onClick={() => remove(connection.id)} className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-sm hover:bg-accent"><Trash2 className="size-3.5" />Remove</button></div></article>)}{!connections.length ? <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Add a PostgreSQL or MongoDB connection to query your own data.</p> : null}</div>
  </section>;
}
