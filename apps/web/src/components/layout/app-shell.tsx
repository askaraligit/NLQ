import Link from "next/link";
import { Bookmark, ChevronRight, History, LayoutDashboard, MessageSquarePlus, Settings2, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";

const upcomingNavigation = [
  { label: "New query", icon: MessageSquarePlus },
  { label: "Query history", icon: History },
  { label: "Saved queries", icon: Bookmark },
  { label: "Settings", icon: Settings2 },
];

function Sidebar() {
  return (
    <aside className="flex border-b bg-sidebar px-5 py-5 lg:min-h-dvh lg:w-64 lg:shrink-0 lg:flex-col lg:border-r lg:border-b-0 lg:px-5 lg:py-8">
      <div className="w-full">
        <Link href="/" aria-label="NLQ workspace home" className="inline-flex items-center gap-3 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <span className="grid size-10 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <Sparkles className="size-5" aria-hidden="true" />
          </span>
          <span className="text-xl font-semibold tracking-tight">nlq<span className="text-primary">.</span></span>
        </Link>
        <nav aria-label="Workspace navigation" className="mt-6 lg:mt-12">
          <p className="mb-3 px-3 text-[11px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">Workspace</p>
          <ul className="flex flex-wrap gap-1 lg:flex-col lg:gap-1.5">
            <li>
              <Link href="/" aria-current="page" className="flex items-center gap-3 rounded-lg bg-accent px-3 py-2.5 text-sm font-medium text-accent-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <LayoutDashboard className="size-4" aria-hidden="true" />Overview
              </Link>
            </li>
            {upcomingNavigation.map(({ label, icon: Icon }) => (
              <li key={label}>
                <span aria-disabled="true" className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-muted-foreground">
                  <Icon className="size-4 shrink-0" aria-hidden="true" />
                  {label}
                  <span className="ml-auto rounded border bg-background/60 px-1.5 py-0.5 text-[10px] leading-none">Soon</span>
                </span>
              </li>
            ))}
          </ul>
        </nav>
      </div>
      <div className="mt-auto hidden pt-16 lg:block">
        <div className="rounded-xl border border-primary/10 bg-background/70 p-4">
          <p className="text-xs font-semibold">Room for better questions.</p>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">Bring your business data into focus, one question at a time.</p>
        </div>
        <p className="mt-5 px-1 text-[11px] text-muted-foreground">Natural language. Clearer insights.</p>
      </div>
    </aside>
  );
}

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="min-h-dvh lg:flex">
      <a href="#main-content" className="sr-only z-50 rounded-lg bg-primary px-4 py-3 text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3">Skip to content</a>
      <Sidebar />
      <div className="min-w-0 flex-1">
        <header className="flex h-20 items-center justify-between gap-3 border-b px-6 md:px-10">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Workspace</span>
            <ChevronRight className="size-3.5 text-muted-foreground" aria-hidden="true" />
            <span className="font-medium">Overview</span>
          </div>
          <Badge variant="outline">Setup preview</Badge>
        </header>
        <main id="main-content" tabIndex={-1} className="mx-auto max-w-6xl px-6 py-10 outline-none md:px-10 md:py-14 xl:px-16">
          {children}
        </main>
      </div>
    </div>
  );
}
