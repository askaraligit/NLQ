"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertCircle, LoaderCircle, Sparkles } from "lucide-react";

import { QueryComposer } from "@/components/query/query-composer";
import { QueryResult } from "@/components/results/query-result";
import { useAuth } from "@/components/auth/auth-provider";
import { getModelOptions, submitQuery } from "@/lib/api/nlq";
import type { NLQQueryResponse } from "@/types/nlq";

export function QueryWorkspace() {
  const { token } = useAuth();
  const searchParams = useSearchParams();
  const [question, setQuestion] = useState(() => searchParams.get("question") ?? "");
  const [result, setResult] = useState<NLQQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, setIsPending] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>(
    () => searchParams.get("conversation") ?? undefined,
  );
  const [model, setModel] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [provider, setProvider] = useState("");

  useEffect(() => {
    if (!token) return;
    getModelOptions(token).then((options) => {
      setModels(options.models);
      setModel((current) => current && options.models.includes(current) ? current : options.defaultModel);
      setProvider(options.provider);
    }).catch(() => undefined);
  }, [token]);

  async function runQuery() {
    const trimmedQuestion = question.trim();
    if (trimmedQuestion.length < 3 || isPending) {
      return;
    }
    setError(null);
    setResult(null);
    setIsPending(true);
    try {
      if (!token) return;
      const next = await submitQuery(trimmedQuestion, token, conversationId, undefined, model || undefined);
      setResult(next);
      setConversationId(next.conversationId);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "We could not complete that query.");
    } finally {
      setIsPending(false);
    }
  }

  return (
    <div className="space-y-8">
      <QueryComposer question={question} isPending={isPending} onQuestionChange={setQuestion} onSubmit={runQuery} model={model} models={models} provider={provider} onModelChange={setModel} />
      {error ? (
        <div role="alert" className="flex gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div><p className="font-medium">Your query could not run</p><p className="mt-1 opacity-90">{error}</p></div>
        </div>
      ) : null}
      {isPending ? (
        <div className="rounded-2xl border bg-card p-8 text-center">
          <LoaderCircle className="mx-auto size-6 animate-spin text-primary" aria-hidden="true" />
          <p className="mt-3 text-sm font-medium">Preparing a safe query</p>
          <p className="mt-1 text-sm text-muted-foreground">We&apos;re checking the schema and running it through the read-only analytics path.</p>
        </div>
      ) : null}
      {result && token ? <QueryResult result={result} token={token} /> : null}
      {!result && !isPending ? (
        <section className="rounded-2xl border border-dashed bg-secondary/25 p-8 text-center sm:p-10">
          <span className="mx-auto grid size-11 place-items-center rounded-xl bg-accent text-primary"><Sparkles className="size-5" aria-hidden="true" /></span>
          <h2 className="mt-4 text-lg font-semibold tracking-tight">Answers will appear here</h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">Ask a question in plain language. You&apos;ll get a result table and the generated SQL behind it.</p>
        </section>
      ) : null}
    </div>
  );
}
