import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { SavedPanel } from "@/components/workspace/saved-panel";
export default function SavedPage() { return <AppShell><RequireAuth><SavedPanel /></RequireAuth></AppShell>; }
