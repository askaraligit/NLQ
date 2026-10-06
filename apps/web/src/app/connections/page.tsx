import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { ConnectionsPanel } from "@/components/workspace/connections-panel";

export default function ConnectionsPage() { return <AppShell><RequireAuth><ConnectionsPanel /></RequireAuth></AppShell>; }
