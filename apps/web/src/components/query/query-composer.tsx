"use client";

import type { FormEvent, KeyboardEvent } from "react";
import { LoaderCircle, SendHorizontal, X } from "lucide-react";

import { Button } from "@/components/ui/button";

const suggestedQuestions = [
  "Show all pending purchase orders",
  "Which products are below their reorder level?",
  "Show monthly sales for 2026",
  "What are the top 10 products by revenue?",
];

type QueryComposerProps = {
  question: string;
  isPending: boolean;
  onQuestionChange: (question: string) => void;
  onSubmit: () => void;
  model: string;
  models: string[];
  provider: string;
  onModelChange: (model: string) => void;
};

export function QueryComposer({
  question,
  isPending,
  onQuestionChange,
  onSubmit,
  model,
  models,
  provider,
  onModelChange,
}: Readonly<QueryComposerProps>) {
  const canSubmit = question.trim().length >= 3 && !isPending;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (canSubmit) {
      onSubmit();
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (canSubmit) {
        event.currentTarget.form?.requestSubmit();
      }
    }
  }

  return (
    <section aria-labelledby="query-title" className="rounded-2xl border border-primary/15 bg-card p-5 shadow-[0_18px_45px_-35px_#17665980] sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold tracking-[0.14em] text-primary uppercase">New analysis</p>
          <h1 id="query-title" className="mt-2 text-2xl font-semibold tracking-tight">Ask your business data</h1>
        </div>
        <span className="rounded-full bg-secondary px-3 py-1.5 text-xs text-secondary-foreground">Read-only queries</span>
      </div>
      <form className="mt-5" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="query-question">Ask a business question</label>
        <div className="rounded-xl border border-input bg-background p-3 transition-shadow focus-within:border-primary/45 focus-within:ring-2 focus-within:ring-primary/15">
          <textarea
            id="query-question"
            value={question}
            onChange={(event) => onQuestionChange(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isPending}
            rows={4}
            maxLength={1000}
            placeholder="Ask anything about your business data…"
            className="min-h-28 w-full resize-y bg-transparent px-1 py-1 text-base leading-7 outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
            aria-describedby="query-guidance"
          />
          <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3">
            <p id="query-guidance" className="text-xs text-muted-foreground">Enter to run · Shift + Enter for a new line</p>
            <div className="flex items-center gap-2">
              {models.length > 1 ? <label className="text-xs text-muted-foreground">Model<select value={model} onChange={(event) => onModelChange(event.target.value)} disabled={isPending} className="ml-2 rounded-md border bg-background px-2 py-1 text-foreground"><option value={model}>{model}</option>{models.filter((item) => item !== model).map((item) => <option key={item} value={item}>{item}</option>)}</select></label> : <span className="text-xs text-muted-foreground">{provider}: {model}</span>}
              {question ? (
                <Button type="button" variant="ghost" size="sm" onClick={() => onQuestionChange("")} disabled={isPending}>
                  <X aria-hidden="true" />Clear
                </Button>
              ) : null}
              <Button type="submit" disabled={!canSubmit}>
                {isPending ? <LoaderCircle className="animate-spin" aria-hidden="true" /> : <SendHorizontal aria-hidden="true" />}
                {isPending ? "Running query" : "Run query"}
              </Button>
            </div>
          </div>
        </div>
      </form>
      <div className="mt-5" aria-label="Suggested questions">
        <p className="text-xs font-medium text-muted-foreground">Try a question</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {suggestedQuestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              disabled={isPending}
              onClick={() => onQuestionChange(suggestion)}
              className="rounded-full border bg-background px-3 py-1.5 text-left text-xs text-secondary-foreground transition-colors hover:border-primary/30 hover:bg-accent hover:text-accent-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
