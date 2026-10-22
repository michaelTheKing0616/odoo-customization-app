"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { JobAutopilotBriefPanel } from "@/components/job-autopilot/JobAutopilotBriefPanel";
import { JobAutopilotConfigPanel } from "@/components/job-autopilot/JobAutopilotConfigPanel";
import { JobAutopilotHandoffBar } from "@/components/job-autopilot/JobAutopilotHandoffBar";
import { JobAutopilotHonestyBanners } from "@/components/job-autopilot/JobAutopilotHonestyBanners";
import { JobAutopilotProgress } from "@/components/job-autopilot/JobAutopilotProgress";
import { JobAutopilotScorecard } from "@/components/job-autopilot/JobAutopilotScorecard";
import { JobAutopilotShell } from "@/components/job-autopilot/JobAutopilotShell";
import { JobAutopilotPacketCard } from "@/components/job-autopilot/JobAutopilotPacketCard";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import {
  jobAutopilotErrorGuide,
  jobAutopilotErrorTitle,
  jobAutopilotGate,
  jobAutopilotJourneyFromState,
  jobAutopilotProductionRefuseMessage,
  jobProgressLabel,
  jobRunBlocked,
  jobRunStepCurrent,
  type JobWriteMode,
} from "@/lib/job-autopilot-journey";
import type { JobPacket } from "@/lib/api";
import "@/styles/studio-refinement.css";

const DEMO_PACKET: JobPacket = {
  prompt: "Recording studio in Lagos",
  domain_label: "Services",
  actors: ["studio manager"],
  processes: ["book", "invoice"],
  documents: ["contacts"],
  stock_apps: ["crm", "sale_management", "account"],
  custom_residuals: [],
  data_files: [],
  country_code: "NG",
  l10n_module: "l10n_ng",
  company_name: "Lagos Sessions",
  currency: "NGN",
  warehouse_needed: false,
  roles: ["accountant"],
  risks: [],
  decision_record: ["Stock-first: CRM + Sales + Invoicing"],
  warnings: [],
  planner: "rules",
  scorecard_note: "Completeness is not this bar.",
  connectors: ["payments", "messaging"],
  structured_brief: "Recording studio. Book sessions. Invoice in naira.",
};

function JobAutopilotHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const modeParam = searchParams.get("mode");
  const state = searchParams.get("state") || (modeParam === "production" ? "production" : "scorecard");
  const writeMode = (
    state === "production" || modeParam === "production" ? "production" : "standard"
  ) as JobWriteMode;
  const isOnline = state === "online";
  const sandbox = writeMode !== "production" && !isOnline;
  const gate = jobAutopilotGate({
    writeMode,
    sandbox,
    localSandboxUrl: sandbox,
  });
  const running = state === "progress";
  const hasResult = state === "scorecard" || state === "promote";
  const journey = jobAutopilotJourneyFromState({
    busy: running ? "run" : null,
    hasResult: hasResult || state === "scorecard",
    promoteReady: state === "promote" || state === "scorecard",
    failed: state === "error",
  });
  const productionError =
    writeMode === "production" ? jobAutopilotProductionRefuseMessage() : null;
  const errorGuide = productionError ? jobAutopilotErrorGuide(productionError) : null;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <JobAutopilotShell
      connectionId="e2e-mock"
      connectionName={
        writeMode === "production"
          ? "Client production"
          : isOnline
            ? "acme.odoo.com"
            : "Lab 19"
      }
      writeMode={writeMode}
      journey={journey}
    >
      <JobAutopilotHonestyBanners
        gate={gate}
        isOdooOnline={isOnline}
      />
      {productionError ? (
        <div className="job-error-block" data-testid="job-autopilot-error-block">
          <ErrorNotice message={productionError} title={jobAutopilotErrorTitle(productionError)} />
          {errorGuide ? (
            <div className="job-empty-guide mt-2" data-testid="job-error-guide">
              <p className="job-empty-what">{errorGuide.what}</p>
              <p className="job-empty-why">{errorGuide.why}</p>
              <p className="job-empty-next">{errorGuide.next}</p>
            </div>
          ) : null}
        </div>
      ) : null}
      {running ? (
        <JobAutopilotProgress
          label={jobProgressLabel({ busy: "run", stepLabel: "Stock bootstrap", elapsedMinutes: 2 })}
          stages={["packet", "stock"]}
          currentStep={jobRunStepCurrent(["packet", "stock"], "run")}
        />
      ) : (
        <>
          <JobAutopilotBriefPanel
            prompt={
              state === "brief" || state === "empty"
                ? ""
                : "Recording studio in Lagos. Clients book sessions. We invoice in naira."
            }
            files={[]}
            busy={null}
            runBlocked={jobRunBlocked(writeMode) || gate.runBlocked}
            runBlockedReason={gate.runBlocked ? gate.body : undefined}
            runIsPrimary={!hasResult}
            onPromptChange={() => undefined}
            onFilesChange={() => undefined}
            onPlan={() => undefined}
            onRun={() => undefined}
          />
          {state !== "brief" && state !== "empty" && state !== "production" ? (
            <JobAutopilotPacketCard
              packet={DEMO_PACKET}
              connectionKind={isOnline ? "online" : "sandbox"}
              sandbox={sandbox}
            />
          ) : null}
          {hasResult ? (
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
              connectorsDetected={DEMO_PACKET.connectors}
              connectorsResult={{
                ran: ["payments"],
                failed: [],
                skipped_ids: ["messaging"],
                steps: [{ name: "payments", ok: true }],
              }}
            />
          ) : null}
          <JobAutopilotConfigPanel
            configPacket={null}
            fingerprint={null}
            configDiff={null}
            busy={null}
            onFingerprint={() => undefined}
            onCaptureSettings={() => undefined}
            onDryRun={() => undefined}
            onApply={() => undefined}
            onDownload={() => undefined}
          />
          <JobAutopilotHandoffBar
            connectionId="e2e-mock"
            targets={[]}
            targetId=""
            sandboxUrl={sandbox ? "http://127.0.0.1:18069" : null}
            sandboxLabel="Open sandbox"
            hasResult={hasResult}
            promoteReady={hasResult}
            hasResidualZip={false}
            showModuleSpec={false}
            busy={null}
            onTargetChange={() => undefined}
            onPromote={() => undefined}
            onDownloadReport={() => undefined}
            onDownloadPdf={() => undefined}
          />
        </>
      )}
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
