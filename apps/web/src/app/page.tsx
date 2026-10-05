import { AppShell } from "@/components/layout/app-shell";
import { RequireAuth } from "@/components/auth/require-auth";
import { QueryWorkspace } from "@/components/query/query-workspace";

export default function HomePage() {
  return (
    <AppShell>
      <RequireAuth><QueryWorkspace /></RequireAuth>
    </AppShell>
  );
}
