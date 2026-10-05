"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";

export function SqlViewer({ sql }: Readonly<{ sql: string }>) {
  const [copied, setCopied] = useState(false);

  async function copySql() {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  return (
    <div className="overflow-hidden rounded-xl border bg-[#18302d] text-[#e8f4ed]">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
        <span className="font-mono text-xs text-white/65">Generated SQL · read only</span>
        <Button type="button" size="sm" variant="ghost" onClick={copySql} className="h-7 text-white/80 hover:bg-white/10 hover:text-white">
          {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}{copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre className="max-h-96 overflow-auto p-4 font-mono text-xs leading-6 whitespace-pre-wrap"><code>{sql}</code></pre>
    </div>
  );
}
