"use client";

import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import { ExpertPanel } from "@/components/expert/ExpertPanel";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { ExpertDiagnoseListener } from "@/lib/expert-diagnostics";
import { ShellProvider } from "@/context/ShellContext";
import { QueryProvider } from "@/providers/QueryProvider";

/** E2E harness for explain-this + error-diagnose expert flows (REM-9). */
export default function ExpertHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <QueryProvider>
      <ShellProvider connectionId="e2e-expert-conn">
        <TooltipProvider>
          <ExpertDiagnoseListener />
          <main className="space-y-6 p-6" data-testid="expert-harness">
            <h1 className="text-lg font-semibold">Expert UX harness</h1>
            <section data-testid="builder-explain-section">
              <h2 className="text-sm font-medium">Builder field</h2>
              <div className="mt-2 flex items-center gap-2">
                <span className="font-mono text-sm">x_status</span>
                <ExplainThisButton question="What does the x_status selection field control?" />
              </div>
            </section>
            <section data-testid="error-diagnose-section">
              <ErrorNotice message="AccessError: You are not allowed to modify 'res.partner' records." />
            </section>
            <ExpertPanel />
          </main>
        </TooltipProvider>
      </ShellProvider>
    </QueryProvider>
  );
}
