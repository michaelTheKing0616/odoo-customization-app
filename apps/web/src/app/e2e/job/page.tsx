"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { JobAutopilotBriefPanel } from "@/components/job-autopilot/JobAutopilotBriefPanel";
import { JobAutopilotHandoffBar } from "@/components/job-autopilot/JobAutopilotHandoffBar";
import { JobAutopilotHonestyBanners } from "@/components/job-autopilot/JobAutopilotHonestyBanners";
import { JobAutopilotScorecard } from "@/components/job-autopilot/JobAutopilotScorecard";
import { JobAutopilotShell } from "@/components/job-autopilot/JobAutopilotShell";
import {
  jobAutopilotGate,
  jobAutopilotJourneyFromState,
  jobRunBlocked,
  type JobWriteMode,
} from "@/lib/job-autopilot-journey";
import "@/styles/studio-refinement.css";

function JobAutopilotHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const writeMode = (searchParams.get("mode") === "production" ? "production" : "standard") as JobWriteMode;
  const sandbox = writeMode !== "production";
  const gate = jobAutopilotGate({
    writeMode,
    sandbox,
    localSandboxUrl: sandbox,
  });
  const journey = jobAutopilotJourneyFromState({
    hasResult: sandbox,
    promoteReady: sandbox,
  });

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <JobAutopilotShell
      connectionId="e2e-mock"
      connectionName={writeMode === "production" ? "Client production" : "Lab 19"}
      writeMode={writeMode}
      journey={journey}
    >
      <JobAutopilotHonestyBanners gate={gate} />
      <JobAutopilotBriefPanel
        prompt="Recording studio in Lagos. Clients book sessions. We invoice in naira."
        files={[]}
        busy={null}
        runBlocked={jobRunBlocked(writeMode) || gate.runBlocked}
        runBlockedReason={gate.runBlocked ? gate.body : undefined}
        onPromptChange={() => undefined}
        onFilesChange={() => undefined}
        onPlan={() => undefined}
        onRun={() => undefined}
      />
      {sandbox ? (
        <JobAutopilotScorecard
          scorecard={{
            stack_fit: 8.2,
            stock_coverage: 9.1,
            data_load: 7.4,
            process_smoke: 9.0,
            overall: 8.4,
            findings: [],
            modulespec_completeness_note: "Completeness is not this bar.",
          }}
          smoke={{
            ok: true,
            steps: [{ name: "quote→invoice", ok: true, detail: "SO confirmed, invoice posted" }],
            named_process: "quote→confirm→invoice",
            message: "RPC smoke passed",
          }}
          promoteReady
        />
      ) : null}
      <JobAutopilotHandoffBar
        connectionId="e2e-mock"
        targets={[]}
        targetId=""
        sandboxUrl={sandbox ? "http://127.0.0.1:18069" : null}
        sandboxLabel="Open sandbox"
        hasResult={sandbox}
        promoteReady={sandbox}
        hasResidualZip={false}
        showModuleSpec={false}
        busy={null}
        onTargetChange={() => undefined}
        onPromote={() => undefined}
        onDownloadReport={() => undefined}
        onDownloadPdf={() => undefined}
      />
    </JobAutopilotShell>
  );
}

export default function JobAutopilotE2ePage() {
  return (
    <Suspense fallback={<p className="p-8">Loading Job Autopilot harness…</p>}>
      <JobAutopilotHarnessInner />
    </Suspense>
  );
}
