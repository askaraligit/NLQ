import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";
import { SettingsPanel } from "@/components/workspace/settings-panel";
export default function SettingsPage() { return <AppShell><RequireAuth><SettingsPanel /></RequireAuth></AppShell>; }
