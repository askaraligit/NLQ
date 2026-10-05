import { ArrowDown, ArrowRight, ChartNoAxesCombined, Database, MessageSquareText, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const workspaceSteps = [
  {
    number: "01",
    icon: Database,
    title: "Start with your data",
    description: "Bring sales, purchasing, and inventory together in a shared analytics workspace.",
  },
  {
    number: "02",
    icon: MessageSquareText,
    title: "Ask in your own words",
    description: "Turn a business question into a starting point. No SQL knowledge needed.",
  },
  {
    number: "03",
    icon: ChartNoAxesCombined,
    title: "Find a clearer answer",
    description: "Explore results through tables, visualizations, and concise explanations.",
  },
];

function WelcomeIllustration() {
  return (
    <div aria-hidden="true" className="workspace-grid relative hidden h-52 w-60 shrink-0 items-center justify-center overflow-hidden rounded-full lg:flex">
      <div className="absolute size-44 rounded-full border border-primary/10" />
      <div className="absolute size-60 rounded-full border border-primary/5" />
      <div className="relative grid size-24 rotate-[-8deg] place-items-center rounded-3xl border border-primary/10 bg-white shadow-[0_12px_36px_-12px_#17665940]">
        <Sparkles className="size-10 text-primary" strokeWidth={1.5} />
      </div>
      <div className="absolute top-5 left-7 grid size-11 rotate-[-10deg] place-items-center rounded-xl border bg-card shadow-xs"><MessageSquareText className="size-5 text-muted-foreground" /></div>
      <div className="absolute right-5 bottom-7 grid size-12 rotate-[9deg] place-items-center rounded-xl border bg-card shadow-xs"><ChartNoAxesCombined className="size-6 text-primary" /></div>
    </div>
  );
}

export function WorkspaceWelcome() {
  return (
    <div className="space-y-10 md:space-y-12">
      <section aria-labelledby="welcome-title" className="flex items-center justify-between gap-8">
        <div className="max-w-xl">
          <p className="mb-4 text-xs font-semibold tracking-[0.14em] text-primary uppercase">Meet your analytics workspace</p>
          <h1 id="welcome-title" className="max-w-lg text-4xl leading-[1.15] font-semibold tracking-[-0.04em] sm:text-5xl">Good questions.<br /><span className="text-primary">Clearer decisions.</span></h1>
          <p className="mt-6 max-w-md text-base leading-7 text-muted-foreground">A new way to explore your business data, with questions that come naturally.</p>
          <Button asChild variant="outline" className="mt-7 bg-card">
            <a href="#workspace-guide">Explore the workspace<ArrowDown aria-hidden="true" /></a>
          </Button>
        </div>
        <WelcomeIllustration />
      </section>

      <Card className="border-primary/15 bg-gradient-to-br from-white to-secondary/60 shadow-none">
        <CardHeader className="flex flex-col gap-5 sm:flex-row sm:items-start sm:gap-4">
          <div className="grid size-11 shrink-0 place-items-center rounded-xl border border-primary/10 bg-card text-primary"><Database className="size-5" aria-hidden="true" /></div>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <CardTitle>Your workspace is taking shape</CardTitle>
              <Badge variant="secondary">Data setup pending</Badge>
            </div>
            <CardDescription className="max-w-2xl">This is an early preview of your workspace. Business data and natural-language queries aren&apos;t available yet.</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="sm:pl-[5.25rem]">
          <p className="flex items-center gap-2 text-xs font-medium text-primary"><ArrowRight className="size-3.5 shrink-0" aria-hidden="true" />Next up: the business data foundation</p>
        </CardContent>
      </Card>

      <section id="workspace-guide" aria-labelledby="guide-title" className="scroll-mt-8">
        <div className="mb-5 flex flex-wrap items-baseline justify-between gap-3">
          <h2 id="guide-title" className="text-lg font-semibold tracking-tight">From question to understanding</h2>
          <span className="text-xs text-muted-foreground">Coming as the workspace grows</span>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {workspaceSteps.map(({ number, icon: Icon, title, description }) => (
            <Card key={number} className="shadow-none">
              <CardHeader className="pb-4">
                <div className="mb-5 flex items-center justify-between">
                  <Icon className="size-5 text-primary" strokeWidth={1.7} aria-hidden="true" />
                  <span className="font-mono text-xs text-muted-foreground">{number}</span>
                </div>
                <CardTitle className="text-sm">{title}</CardTitle>
                <CardDescription className="text-[13px]">{description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>
      <p className="border-t pt-5 text-xs leading-5 text-muted-foreground">Your future home for sales, purchasing, inventory, and the questions that connect them.</p>
    </div>
  );
}
