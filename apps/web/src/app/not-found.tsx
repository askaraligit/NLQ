import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="grid min-h-dvh place-items-center px-6">
      <div className="max-w-md text-center">
        <p className="mb-4 font-mono text-sm text-primary">404</p>
        <h1 className="text-3xl font-semibold tracking-tight">This page isn&apos;t here.</h1>
        <p className="mt-4 text-muted-foreground">Head back to your workspace to find your way.</p>
        <Button asChild className="mt-8">
          <Link href="/"><ArrowLeft aria-hidden="true" />Back to workspace</Link>
        </Button>
      </div>
    </main>
  );
}
