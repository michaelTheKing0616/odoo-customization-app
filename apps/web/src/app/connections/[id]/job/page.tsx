"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  ConfirmationRequiredError,
  Connection,
  JobAutopilotContract,
  JobAutopilotPacketOut,
  JobAutopilotQueued,
  JobAutopilotResult,
  JobPacket,
  JobRow,
  ConfigPacketDiff,
  InstanceFingerprint,
} from "@/lib/api";
import { JobPollError, pollJob } from "@/lib/jobs";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { readJobAutopilotBrief } from "@/lib/job-brief-handoff";
import {
  classifyJobAutopilotResume,
  forgetJobAutopilot,
  jobResumeNotice,
  readRememberedJobAutopilot,
  rememberJobAutopilot,
} from "@/lib/job-autopilot-resume";
import { odooMenuUrl, odooRecordUrl, isLocalSandboxUrl } from "@/lib/odoo-urls";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { JobAutopilotShell } from "@/components/job-autopilot/JobAutopilotShell";
import { JobAutopilotHonestyBanners } from "@/components/job-autopilot/JobAutopilotHonestyBanners";
import { JobAutopilotBriefPanel } from "@/components/job-autopilot/JobAutopilotBriefPanel";
import { JobAutopilotPacketCard } from "@/components/job-autopilot/JobAutopilotPacketCard";
import { JobAutopilotProgress } from "@/components/job-autopilot/JobAutopilotProgress";
import { JobAutopilotRunLedger } from "@/components/job-autopilot/JobAutopilotRunLedger";
import { JobAutopilotScorecard } from "@/components/job-autopilot/JobAutopilotScorecard";
import { JobAutopilotDeliveryLedger } from "@/components/job-autopilot/JobAutopilotDeliveryLedger";
import { JobAutopilotHandoffBar } from "@/components/job-autopilot/JobAutopilotHandoffBar";
import { JobAutopilotConfigPanel } from "@/components/job-autopilot/JobAutopilotConfigPanel";
import {
  deliveryReportMarkdown,
  hasResidualModuleSpec,
  isStockOnlyPacket,
  jobAutopilotErrorTitle,
  jobAutopilotGate,
  jobAutopilotJourneyFromState,
  jobAutopilotObserverRefuseMessage,
  jobAutopilotProductionRefuseMessage,
  jobProgressLabel,
  jobRunBlocked,
  jobRunStepCurrent,
  residualZipBase64,
  sandboxOpenLabel,
  type JobAutopilotBusy,
} from "@/lib/job-autopilot-journey";
import "@/styles/studio-refinement.css";

const CONFIRM_PHRASE = "I understand the risks";
const AUTOPILOT_POLL_MS = 3_000;
/** Last-resort only — backend job cap is 45 min; poll until that terminal status. */
const AUTOPILOT_POLL_ATTEMPTS = 2_400;

function isAutopilotQueued(
  out: JobAutopilotResult | JobAutopilotQueued,
): out is JobAutopilotQueued {
  return "queued" in out && out.queued === true && Boolean(out.job_id);
}

function resultFromJobRow(row: JobRow): JobAutopilotResult | null {
  const raw = row.result;
  if (!raw || typeof raw !== "object") return null;
  const candidate = raw as unknown as JobAutopilotResult;
  if (!candidate.packet) return null;
  return candidate;
}

async function attachJobArtifacts(
  jobId: string,
  out: JobAutopilotResult,
): Promise<JobAutopilotResult> {
  if (out.custom && !out.custom.zip_base64) {
    try {
      const art = await api.getJobArtifact(jobId);
      if (art.zip_base64) out.custom.zip_base64 = art.zip_base64;
      if (art.elite_zip_base64 && out.custom.elite && typeof out.custom.elite === "object") {
        out.custom.elite = { ...out.custom.elite, zip_base64: art.elite_zip_base64 };
      }
    } catch {
      /* Promote can still run stock-only if the zip sidecar is missing. */
    }
  }
  return out;
}

async function excerptsFromFiles(files: File[]): Promise<Array<{ filename: string; text: string }>> {
  const out: Array<{ filename: string; text: string }> = [];
  for (const f of files) {
    try {
      const text = (await f.text()).slice(0, 8000);
      out.push({ filename: f.name, text });
    } catch {
      out.push({ filename: f.name, text: "" });
    }
  }
  return out;
}

export default function JobAutopilotPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  useSyncShellContext({ route: "job-autopilot" });

  const [connection, setConnection] = useState<Connection | null>(null);
  const [targets, setTargets] = useState<Connection[]>([]);
  const [targetId, setTargetId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [packetOut, setPacketOut] = useState<JobAutopilotPacketOut | null>(null);
  const [result, setResult] = useState<JobAutopilotResult | null>(null);
  const [contract, setContract] = useState<JobAutopilotContract | null>(null);
  const [busy, setBusy] = useState<JobAutopilotBusy>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepLabel, setStepLabel] = useState<string | null>(null);
  const [elapsedMinutes, setElapsedMinutes] = useState(0);
  const [runFailed, setRunFailed] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [applyPacketOpen, setApplyPacketOpen] = useState(false);
  const [fingerprint, setFingerprint] = useState<InstanceFingerprint | null>(null);
  const [configDiff, setConfigDiff] = useState<ConfigPacketDiff | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<{
    warning: string;
    risks: string[];
    phrase: string;
  } | null>(null);
  const resumeLock = useRef(false);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch(() => setConnection(null));
    api
      .listConnections()
      .then((rows) => setTargets(rows.filter((c) => c.id !== connectionId)))
      .catch(() => setTargets([]));
    api
      .jobAutopilotContract(connectionId)
      .then(setContract)
      .catch(() => setContract(null));
  }, [connectionId]);

  useEffect(() => {
    const handed = readJobAutopilotBrief(connectionId);
    if (!handed) return;
    let filled = false;
    setPrompt((current) => {
      if (current.trim()) return current;
      filled = true;
      return handed;
    });
    if (filled) {
      setNotice("Brief carried from Draft Studio. Review, then Plan packet / Run Autopilot.");
    }
  }, [connectionId]);

  useEffect(() => {
    resumeLock.current = false;
  }, [connectionId]);

  const packet: JobPacket | null = result?.packet ?? packetOut?.packet ?? null;
  const sandbox = result?.sandbox ?? packetOut?.sandbox ?? false;
  const production = connection?.write_mode === "production";
  const observer = connection?.write_mode === "observer";
  const localSandbox = Boolean(connection?.url && isLocalSandboxUrl(connection.url));
  const gate = jobAutopilotGate({
    writeMode: connection?.write_mode,
    sandbox,
    localSandboxUrl: localSandbox,
  });
  const runBlocked = jobRunBlocked(connection?.write_mode);
  const journey = jobAutopilotJourneyFromState({
    busy,
    hasPacket: Boolean(packet),
    hasResult: Boolean(result),
    promoteReady: Boolean(result?.promote_ready),
    refused: Boolean(result?.refused),
    failed: runFailed || Boolean(result?.refused),
  });

  const sandboxUrl = useMemo(() => {
    const base = connection?.url;
    if (!base) return null;
    const model = result?.smoke?.open_model;
    const rid = result?.smoke?.open_id;
    const actionId = result?.smoke?.open_action_id ?? null;
    if (model && rid) {
      return odooRecordUrl(base, model, rid, actionId);
    }
    const menuId = result?.custom?.root_menu_id;
    const menuActionId = result?.custom?.open_action_id;
    if (menuId) return odooMenuUrl(base, menuId, menuActionId);
    return `${base.replace(/\/$/, "")}/web`;
  }, [
    connection?.url,
    result?.smoke?.open_model,
    result?.smoke?.open_id,
    result?.smoke?.open_action_id,
    result?.custom?.open_action_id,
    result?.custom?.root_menu_id,
  ]);

  async function followQueuedJob(jobId: string): Promise<JobAutopilotResult> {
    rememberJobAutopilot(connectionId, jobId);
    const job = await pollJob(jobId, {
      fetchJob: api.getJob,
      intervalMs: AUTOPILOT_POLL_MS,
      maxAttempts: AUTOPILOT_POLL_ATTEMPTS,
      untilTerminal: true,
      onUpdate: (row) => {
        const label = row.result?.step_label;
        const startedAt = row.created_at ? Date.parse(row.created_at) : Number.NaN;
        const minutes = Number.isFinite(startedAt)
          ? Math.max(0, Math.round((Date.now() - startedAt) / 60_000))
          : 0;
        setElapsedMinutes(minutes);
        if (typeof label === "string" && label) {
          setStepLabel(label);
          setNotice(`Autopilot: ${label} (${minutes} min)…`);
        }
        const stages = row.result?.stages;
        if (Array.isArray(stages) && stages.every((s) => typeof s === "string")) {
          setResult((prev) => (prev ? { ...prev, stages: stages as string[] } : null));
        }
      },
    });
    const raw = resultFromJobRow(job);
    if (!raw) {
      throw new Error(job.error || "Autopilot finished without a result payload.");
    }
    const out = await attachJobArtifacts(job.id, raw);
    forgetJobAutopilot(connectionId);
    return out;
  }

  async function resumeRememberedJob(): Promise<void> {
    const jobId = readRememberedJobAutopilot(connectionId);
    if (!jobId) return;
    try {
      const row = await api.getJob(jobId);
      const kind = classifyJobAutopilotResume(row, connectionId);
      if (kind === "stale") {
        forgetJobAutopilot(connectionId);
        setNotice(jobResumeNotice("stale"));
        return;
      }
      if (kind === "running") {
        setBusy("run");
        setError(null);
        setRunFailed(false);
        setNotice(jobResumeNotice("running"));
        const out = await followQueuedJob(jobId);
        setResult(out);
        setNotice(out.message);
        if (out.refused) setError(out.refuse_reason || out.message);
        return;
      }
      if (kind === "succeeded") {
        const raw = resultFromJobRow(row);
        if (raw) {
          setResult(await attachJobArtifacts(jobId, raw));
          setNotice(jobResumeNotice("succeeded"));
        } else {
          setNotice(jobResumeNotice("stale"));
        }
        forgetJobAutopilot(connectionId);
        return;
      }
      forgetJobAutopilot(connectionId);
      const failed = resultFromJobRow(row);
      if (failed) setResult(failed);
      setRunFailed(true);
      setError(row.error || "Last Autopilot job did not finish.");
      setNotice(jobResumeNotice("failed"));
    } catch (err) {
      forgetJobAutopilot(connectionId);
      if (err instanceof JobPollError) {
        setRunFailed(true);
        setError(err.message);
        setNotice(jobResumeNotice("failed"));
        return;
      }
      setNotice(jobResumeNotice("stale"));
    } finally {
      setBusy((current) => (current === "run" ? null : current));
      setStepLabel(null);
    }
  }

  useEffect(() => {
    if (resumeLock.current) return;
    if (!readRememberedJobAutopilot(connectionId)) return;
    resumeLock.current = true;
    void resumeRememberedJob();
  }, [connectionId]);

  async function planPacket() {
    if (!prompt.trim()) {
      setError("Describe the job in natural language first.");
      return;
    }
    setBusy("packet");
    setError(null);
    setNotice(null);
    setRunFailed(false);
    setResult(null);
    try {
      const excerpts = files.length ? await excerptsFromFiles(files) : [];
      const out = await api.jobAutopilotPacket(connectionId, {
        prompt: prompt.trim(),
        file_excerpts: excerpts,
        use_llm: null,
      });
      setPacketOut(out);
      setNotice(out.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function runJob(confirmAdvanced = false, phrase: string | null = null) {
    if (!prompt.trim()) {
      setError("Describe the job in natural language first.");
      return;
    }
    if (production) {
      setRunFailed(true);
      setError(jobAutopilotProductionRefuseMessage());
      return;
    }
    if (observer) {
      setRunFailed(true);
      setError(jobAutopilotObserverRefuseMessage());
      return;
    }
    setBusy("run");
    setError(null);
    setNotice(null);
    setRunFailed(false);
    setStepLabel(null);
    setElapsedMinutes(0);
    try {
      const started = files.length
        ? await api.jobAutopilotRunFiles(connectionId, {
            prompt: prompt.trim(),
            files,
            confirm_advanced: confirmAdvanced,
            confirm_phrase: phrase,
          })
        : await api.jobAutopilotRun(connectionId, {
            prompt: prompt.trim(),
            packet: packetOut?.packet ? (packetOut.packet as unknown as Record<string, unknown>) : null,
            confirm_advanced: confirmAdvanced,
            confirm_phrase: phrase,
          });
      let out: JobAutopilotResult;
      if (isAutopilotQueued(started)) {
        setNotice(started.message);
        out = await followQueuedJob(started.job_id);
      } else {
        out = started;
      }
      setResult(out);
      setNotice(out.message);
      if (out.refused) setError(out.refuse_reason || out.message);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setPendingConfirm({
          warning: err.warning,
          risks: err.risks,
          phrase: err.confirm_phrase || CONFIRM_PHRASE,
        });
        setConfirmOpen(true);
        return;
      }
      setRunFailed(true);
      setError(err instanceof Error ? err.message : String(err));
      if (
        err instanceof JobPollError &&
        err.job &&
        ["failed", "timeout", "cancelled", "interrupted"].includes(err.job.status)
      ) {
        forgetJobAutopilot(connectionId);
      }
    } finally {
      setBusy(null);
      setStepLabel(null);
    }
  }

  async function promote(phrase: string) {
    const zip = residualZipBase64(result);
    if (!zip) {
      setNotice(
        "Stock-only (or no module zip): this sandbox is the delivery. Autopilot will not write production. Download the UAT report; clone or configure prod yourself.",
      );
      setPromoteOpen(false);
      return;
    }
    if (!targetId) {
      setError("Pick a target connection. Promote-to never writes this sandbox onto itself.");
      setPromoteOpen(false);
      return;
    }
    setBusy("promote");
    setError(null);
    try {
      const out = await api.jobAutopilotPromoteTo(connectionId, {
        target_connection_id: targetId,
        zip_base64: zip,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setNotice(out.message || (out.ok ? "Promoted to target." : "Promote did not succeed."));
      if (!out.ok) setError(out.refuse_reason || out.message);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setPendingConfirm({
          warning: err.warning,
          risks: err.risks,
          phrase: err.confirm_phrase || CONFIRM_PHRASE,
        });
        setPromoteOpen(true);
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
      setPromoteOpen(false);
    }
  }

  function downloadReport() {
    if (!result) return;
    const blob = new Blob([deliveryReportMarkdown(result)], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "job-autopilot-uat.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function downloadPdf() {
    if (!result) return;
    setBusy("pdf");
    setError(null);
    try {
      const blob = await api.jobAutopilotReportPdf(connectionId, result);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "job-autopilot-uat.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  const configPacket = result?.config_packet ?? null;
  const applyTargetId = targetId || connectionId;

  async function runFingerprint() {
    setBusy("fingerprint");
    setError(null);
    try {
      const out = await api.jobAutopilotFingerprint(applyTargetId);
      setFingerprint(out.fingerprint);
      setNotice(out.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function captureSettings() {
    setBusy("settings");
    setError(null);
    try {
      const out = await api.jobAutopilotCaptureSettings(connectionId);
      setNotice(out.message);
      setResult((prev) => {
        if (!prev?.config_packet) return prev;
        return {
          ...prev,
          config_packet: {
            ...prev.config_packet,
            settings: { values: out.settings },
          },
        };
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function runConfigDryRun() {
    if (!configPacket) {
      setError("Run Autopilot on the sandbox first so a Config Packet exists.");
      return;
    }
    setBusy("dryrun");
    setError(null);
    try {
      const out = await api.jobAutopilotConfigDryRun(
        applyTargetId,
        configPacket as unknown as Record<string, unknown>,
      );
      setConfigDiff(out.diff);
      setFingerprint(out.fingerprint);
      setNotice(out.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function applyConfigPacket(phrase: string) {
    if (!configPacket) return;
    setBusy("applypacket");
    setError(null);
    try {
      const out = await api.jobAutopilotConfigApply(applyTargetId, {
        packet: configPacket as unknown as Record<string, unknown>,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setNotice(out.message);
      if (!out.ok) setError(out.refuse_reason || out.message);
      if (out.checklist?.length) setConfigDiff((prev) => prev ? { ...prev, checklist: out.checklist } : prev);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setPendingConfirm({
          warning: err.warning,
          risks: err.risks,
          phrase: err.confirm_phrase || CONFIRM_PHRASE,
        });
        setApplyPacketOpen(true);
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
      setApplyPacketOpen(false);
    }
  }

  function downloadConfigPacket() {
    if (!configPacket) return;
    const blob = new Blob([JSON.stringify(configPacket, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `config-packet-${configPacket.sha256 || "draft"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const stages = result?.stages;
  const running = busy === "run";

  return (
    <JobAutopilotShell
      connectionId={connectionId}
      connectionName={connection?.name}
      writeMode={connection?.write_mode}
      journey={journey}
    >
      <JobAutopilotHonestyBanners
        gate={gate}
        showOverviewNote={localSandbox && !production}
        contractNote={contract?.note}
      />

      {error ? (
        <ErrorNotice message={error} title={jobAutopilotErrorTitle(error)} />
      ) : null}
      {notice ? (
        <p className="text-sm text-muted" data-testid="job-autopilot-notice">
          {notice}
        </p>
      ) : null}

      {running ? (
        <JobAutopilotProgress
          label={jobProgressLabel({ busy, stepLabel, elapsedMinutes })}
          stages={stages}
          currentStep={jobRunStepCurrent(stages, busy)}
        />
      ) : (
        <>
          <JobAutopilotBriefPanel
            prompt={prompt}
            files={files}
            busy={busy}
            runBlocked={runBlocked}
            runBlockedReason={gate.runBlocked ? gate.body : undefined}
            onPromptChange={setPrompt}
            onFilesChange={setFiles}
            onPlan={() => void planPacket()}
            onRun={() => void runJob()}
          />

          {packet ? (
            <JobAutopilotPacketCard
              packet={packet}
              connectionKind={result?.connection_kind ?? packetOut?.connection_kind}
              sandbox={sandbox}
            />
          ) : null}

          {result ? (
            <>
              <JobAutopilotRunLedger stages={stages} />
              <JobAutopilotScorecard
                scorecard={result.job_scorecard}
                smoke={result.smoke}
                promoteReady={result.promote_ready}
                stockOnly={isStockOnlyPacket(result.packet)}
                retryCount={result.retry_count}
              />
              <JobAutopilotDeliveryLedger result={result} />
            </>
          ) : null}

          <JobAutopilotConfigPanel
            configPacket={configPacket}
            fingerprint={fingerprint}
            configDiff={configDiff}
            connectionUrl={connection?.url}
            busy={busy}
            onFingerprint={() => void runFingerprint()}
            onCaptureSettings={() => void captureSettings()}
            onDryRun={() => void runConfigDryRun()}
            onApply={() => setApplyPacketOpen(true)}
            onDownload={downloadConfigPacket}
          />

          <JobAutopilotHandoffBar
            connectionId={connectionId}
            targets={targets}
            targetId={targetId}
            sandboxUrl={sandboxUrl}
            sandboxLabel={sandboxOpenLabel(result)}
            hasResult={Boolean(result)}
            promoteReady={Boolean(result?.promote_ready)}
            hasResidualZip={Boolean(residualZipBase64(result))}
            showModuleSpec={hasResidualModuleSpec(result)}
            busy={busy}
            onTargetChange={setTargetId}
            onPromote={() => setPromoteOpen(true)}
            onDownloadReport={downloadReport}
            onDownloadPdf={() => void downloadPdf()}
          />
        </>
      )}

      <ConfirmDialogV2
        open={confirmOpen}
        title="Run Autopilot on this connection"
        warning={pendingConfirm?.warning || "This is not a local sandbox. Confirm to install and apply."}
        risks={pendingConfirm?.risks?.length ? pendingConfirm.risks : ["Installs modules", "May apply custom residual", "May commit ingest"]}
        phrase={pendingConfirm?.phrase || CONFIRM_PHRASE}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => {
          setConfirmOpen(false);
          void runJob(true, phrase);
        }}
        busy={busy === "run"}
      />

      <ConfirmDialogV2
        open={promoteOpen}
        title="Promote stays human"
        warning={
          residualZipBase64(result)
            ? "Promote installs the sandbox zip onto the TARGET connection. Autopilot never runs on production."
            : "This job has no module zip (stock-only or export skipped). The sandbox is the delivery. Do not run Autopilot on production."
        }
        risks={
          residualZipBase64(result)
            ? [
                "Writes a module onto the target Odoo database",
                "Does not clone a production database",
                "Does not replace a full UAT sign-off",
                "Scorecard 10.0 is not go-live quality",
              ]
            : [
                "No zip will be installed",
                "Keep this sandbox; clone or configure production yourself",
                "Autopilot refuses write_mode=production",
              ]
        }
        phrase={CONFIRM_PHRASE}
        riskLevel="danger"
        onCancel={() => setPromoteOpen(false)}
        onConfirm={(phrase) => void promote(phrase)}
        busy={busy === "promote"}
      />

      <ConfirmDialogV2
        open={applyPacketOpen}
        title="Apply Config Packet"
        warning={
          pendingConfirm?.warning ||
          "Applies stock configuration (modules, journals, warehouse, allowlisted Settings, users) onto the TARGET connection. This is not Job Autopilot. Secrets are never written."
        }
        risks={
          pendingConfirm?.risks?.length
            ? pendingConfirm.risks
            : [
                "May install Community modules on the target database",
                "Does not clone a production database",
                "Does not write API keys or SMTP passwords",
                "Taxes are xmlid-verified only",
              ]
        }
        phrase={pendingConfirm?.phrase || CONFIRM_PHRASE}
        riskLevel="danger"
        onCancel={() => setApplyPacketOpen(false)}
        onConfirm={(phrase) => void applyConfigPacket(phrase)}
        busy={busy === "applypacket"}
      />
    </JobAutopilotShell>
  );
}
