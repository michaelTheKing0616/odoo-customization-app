"use client";

import { AskWhyButton } from "@/components/expert/AskWhyButton";
import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import { ExpertOverviewCard } from "@/components/expert/ExpertOverviewCard";
import { ExpertPanel } from "@/components/expert/ExpertPanel";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { ExpertDiagnoseListener } from "@/lib/expert-diagnostics";
import { ShellProvider } from "@/context/ShellContext";
import { QueryProvider } from "@/providers/QueryProvider";
import "@/styles/studio-refinement.css";

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
          <main className="studio-refinement mx-auto max-w-3xl space-y-6 p-6" data-testid="expert-harness">
            <h1 className="text-lg font-semibold tracking-tight">Odoo Expert</h1>
            <p className="text-sm text-muted">
              Harness for explain-this, ask-why, and diagnose. Completeness ≠ Cert ≠ Autopilot. Expert
              never auto-promotes.
            </p>
            <ExpertOverviewCard connectionId="e2e-expert-conn" connectionName="E2E mock" />
            <section data-testid="builder-explain-section">
              <h2 className="text-sm font-medium">Builder field</h2>
              <div className="mt-2 flex items-center gap-2">
                <span className="font-mono text-sm">x_status</span>
                <ExplainThisButton question="What does the x_status selection field control?" />
                <AskWhyButton subject="x_status" context="selection field on the builder canvas" />
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
