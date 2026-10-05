import { AppShell } from "@/components/layout/app-shell";
import { WorkspaceWelcome } from "@/components/layout/workspace-welcome";

export default function HomePage() {
  return (
    <AppShell>
      <WorkspaceWelcome />
    </AppShell>
  );
}
