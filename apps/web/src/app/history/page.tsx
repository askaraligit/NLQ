import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { HistoryPanel } from "@/components/workspace/history-panel";
export default function HistoryPage() { return <AppShell><RequireAuth><HistoryPanel /></RequireAuth></AppShell>; }
