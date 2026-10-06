"use client";

import { useState } from "react";
import { Braces, BookmarkPlus, ChartNoAxesCombined, Database, TableProperties } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AnalyticsChart } from "@/components/charts/analytics-chart";
import { QueryTable } from "@/components/results/query-table";
import { SqlViewer } from "@/components/results/sql-viewer";
import { cn } from "@/lib/utils";
import { saveQuery } from "@/lib/api/workspace";
import type { NLQQueryResponse } from "@/types/nlq";

type ResultTab = "table" | "chart" | "query";

export function QueryResult({ result, token }: Readonly<{ result: NLQQueryResponse; token: string }>) {
  const [activeTab, setActiveTab] = useState<ResultTab>("table");
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  async function save() {
    const name = window.prompt("Name this saved query", result.question.slice(0, 120));
    if (!name?.trim()) return;
    try { await saveQuery(token, result.queryId, name); setSaved(true); setSaveError(null); }
    catch (error) { setSaveError(error instanceof Error ? error.message : "Unable to save query."); }
  }

  return (
    <section aria-labelledby="result-title" className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-[0.14em] text-primary uppercase">Query result</p>
          <h2 id="result-title" className="mt-2 text-xl font-semibold tracking-tight">{result.question}</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={save} disabled={saved} className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-accent disabled:opacity-60"><BookmarkPlus className="size-3.5" />{saved ? "Saved" : "Save"}</button>
          <Badge variant="outline">{result.rows.length} {result.rows.length === 1 ? "row" : "rows"}</Badge>
          <Badge variant="outline">{result.executionTimeMs} ms</Badge>
        </div>
      </div>
      {saveError ? <p role="alert" className="text-sm text-destructive">{saveError}</p> : null}
      <Card className="border-primary/15 bg-gradient-to-br from-card to-accent/40 shadow-none">
        <CardHeader className="flex flex-row gap-4 space-y-0">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground"><Database className="size-5" aria-hidden="true" /></span>
          <div>
            <CardTitle className="text-sm">What we found</CardTitle>
            <p className="mt-1.5 text-sm leading-6 text-secondary-foreground">{result.summary}</p>
          </div>
        </CardHeader>
      </Card>
      <Card className="overflow-hidden shadow-none">
        <div className="flex border-b px-4 pt-3 sm:px-6">
          {(["table", "chart", "query"] as const).map((tab) => {
            const Icon = tab === "table" ? TableProperties : tab === "chart" ? ChartNoAxesCombined : Braces;
            return (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={cn(
                  "inline-flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium capitalize outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                  activeTab === tab ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground",
                )}
                aria-current={activeTab === tab ? "page" : undefined}
              >
                <Icon className="size-4" aria-hidden="true" />{tab}
              </button>
            );
          })}
        </div>
        <CardContent className="p-4 sm:p-6">
          {activeTab === "table" ? <QueryTable columns={result.columns} rows={result.rows} /> : null}
          {activeTab === "chart" ? <AnalyticsChart result={result} /> : null}
          {activeTab === "query" ? <SqlViewer sql={result.sql} language={result.queryLanguage} /> : null}
        </CardContent>
      </Card>
    </section>
  );
}
