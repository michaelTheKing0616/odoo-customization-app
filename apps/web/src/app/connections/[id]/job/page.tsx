"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  ConfirmationRequiredError,
  Connection,
  JobAutopilotPacketOut,
  JobAutopilotQueued,
  JobAutopilotResult,
  JobPacket,
  ConfigPacketDiff,
  InstanceFingerprint,
} from "@/lib/api";
import { JobPollError, pollJob } from "@/lib/jobs";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { InfinityLoop } from "@/components/loading-ui/infinity-loop";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { Textarea } from "@/components/ui/Textarea";
import { EMPTY_STATES, SCORE_BARS } from "@/lib/copy-guide";
import { readJobAutopilotBrief } from "@/lib/job-brief-handoff";
import { odooMenuUrl, odooRecordUrl, isLocalSandboxUrl, checklistOpenHref } from "@/lib/odoo-urls";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";

const CONFIRM_PHRASE = "I understand the risks";
const AUTOPILOT_POLL_MS = 3_000;
/** Last-resort only — backend job cap is 45 min; poll until that terminal status. */
const AUTOPILOT_POLL_ATTEMPTS = 2_400;

function jobStorageKey(connectionId: string): string {
  return `job-autopilot:${connectionId}`;
}

function rememberJob(connectionId: string, jobId: string): void {
  try {
    sessionStorage.setItem(jobStorageKey(connectionId), jobId);
  } catch {
    /* private mode */
  }
}

function forgetJob(connectionId: string): void {
  try {
    sessionStorage.removeItem(jobStorageKey(connectionId));
  } catch {
    /* private mode */
  }
}

function isAutopilotQueued(
  out: JobAutopilotResult | JobAutopilotQueued,
): out is JobAutopilotQueued {
  return "queued" in out && out.queued === true && Boolean(out.job_id);
}

const STAGES = ["packet", "stock", "connectors", "custom", "data", "smoke"] as const;

function stageDone(stages: string[] | undefined, id: string): boolean {
  if (!stages?.length) return false;
  if (id === "custom") return stages.includes("custom") || stages.includes("custom_retry");
  return stages.includes(id);
}

function deliveryReportMarkdown(result: JobAutopilotResult): string {
  return result.report_markdown || [
    "# Job Autopilot UAT report",
    "",
    result.scorecard_note,
    "",
    `Status: ${result.ok ? "smoke passed" : "not ready"}`,
    `Job scorecard overall: ${result.job_scorecard?.overall ?? "n/a"}/10`,
    `Promote ready: ${result.promote_ready ? "yes (human step)" : "no"}`,
    "",
    result.message,
  ].join("\n");
}

function residualZipBase64(result: JobAutopilotResult | null): string | null {
  const direct = result?.custom?.zip_base64;
  if (direct) return direct;
  const elite = result?.custom?.elite;
  if (elite && typeof elite === "object" && typeof (elite as { zip_base64?: string }).zip_base64 === "string") {
    return (elite as { zip_base64: string }).zip_base64;
  }
  return null;
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
  const [busy, setBusy] = useState<"packet" | "run" | "promote" | "pdf" | "fingerprint" | "dryrun" | "applypacket" | "settings" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
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

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch(() => setConnection(null));
    api
      .listConnections()
      .then((rows) => setTargets(rows.filter((c) => c.id !== connectionId)))
      .catch(() => setTargets([]));
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

  const packet: JobPacket | null = result?.packet ?? packetOut?.packet ?? null;
  const sandbox = result?.sandbox ?? packetOut?.sandbox ?? false;
  const production = connection?.write_mode === "production";
  const observer = connection?.write_mode === "observer";

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

  const sandboxLabel = result?.smoke?.invoice_id
    ? "Open smoke invoice"
    : result?.smoke?.sale_order_id
      ? "Open smoke quotation"
      : result?.custom?.root_menu_id
        ? "Open sandbox app"
        : "Open sandbox";

  async function planPacket() {
    if (!prompt.trim()) {
      setError("Describe the job in natural language first.");
      return;
    }
    setBusy("packet");
    setError(null);
    setNotice(null);
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
      setError(
        "Autopilot refuses write_mode=production. Clone a sandbox, run Autopilot there, then Promote.",
      );
      return;
    }
    if (observer) {
      setError("Observer connections cannot install or apply. Switch write_mode to standard on a sandbox.");
      return;
    }
    setBusy("run");
    setError(null);
    setNotice(null);
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
        rememberJob(connectionId, started.job_id);
        setNotice(started.message);
        const job = await pollJob(started.job_id, {
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
            if (typeof label === "string" && label) {
              setNotice(`Autopilot: ${label} (${minutes} min)…`);
            }
            const stages = row.result?.stages;
            if (Array.isArray(stages) && stages.every((s) => typeof s === "string")) {
              setResult((prev) =>
                prev
                  ? { ...prev, stages: stages as string[] }
                  : null,
              );
            }
          },
        });
        out = job.result as unknown as JobAutopilotResult;
        if (!out?.packet) {
          throw new Error(job.error || "Autopilot finished without a result payload.");
        }
        if (out.custom && !out.custom.zip_base64) {
          try {
            const art = await api.getJobArtifact(job.id);
            if (art.zip_base64) out.custom.zip_base64 = art.zip_base64;
            if (art.elite_zip_base64 && out.custom.elite && typeof out.custom.elite === "object") {
              out.custom.elite = { ...out.custom.elite, zip_base64: art.elite_zip_base64 };
            }
          } catch {
            /* Promote can still run stock-only if the zip sidecar is missing. */
          }
        }
        forgetJob(connectionId);
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
      setError(err instanceof Error ? err.message : String(err));
      if (
        err instanceof JobPollError &&
        err.job &&
        ["failed", "timeout", "cancelled", "interrupted"].includes(err.job.status)
      ) {
        forgetJob(connectionId);
      }
    } finally {
      setBusy(null);
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

  return (
    <div className="space-y-6">
      <PageHeader
        title="Job Autopilot"
        description={EMPTY_STATES.jobAutopilot}
      />

      <Callout variant={production ? "danger" : "info"} title="Product contract">
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
          <li>Prefer stock Odoo apps. Custom <code>x_*</code> models are residual only.</li>
          <li>
            Expedited configuration is this page — <strong>Job Autopilot</strong> on a sandbox —
            then the Config Packet replay on the client. Instance Config is the manual knob, not
            the fast path.
          </li>
          <li>Autopilot writes a sandbox (or staging with confirm). Production Autopilot is refused.</li>
          <li>Done bar is RPC process smoke (quote→confirm→invoice-from-SO; Purchase/POS/CRM probes when those apps are named), not ModuleSpec completeness.</li>
          <li>{SCORE_BARS.completeness}</li>
          <li>{SCORE_BARS.certification}</li>
          <li>
            After smoke: (1) Promote residual <em>module zip</em> if any, (2) Apply Config Packet
            delta on the client with the confirm phrase. Secrets stay paste-in-Odoo.
          </li>
        </ul>
      </Callout>

      {connection && isLocalSandboxUrl(connection.url) && !production ? (
        <Callout variant="info" title="Overview checklist is not this job">
          <p className="text-sm">
            The Overview <strong>production readiness</strong> panel (health, least-privilege,
            backup download) gates production write mode only. It does not score or block
            sandbox Autopilot. Amber bootstrap warnings on this page are the job signal.
          </p>
        </Callout>
      ) : null}

      {error ? <ErrorNotice message={error} /> : null}
      {notice ? (
        <p className="text-sm text-muted" data-testid="job-autopilot-notice">
          {notice}
        </p>
      ) : null}

      <Card>
        <div className="space-y-4 p-4">
          <Textarea
            label="Job brief"
            hint="Natural language: who you are, what to sell/stock/invoice, country, and any custom document stock apps do not cover. Opening Job Autopilot from a stock-first Draft Studio result fills this from that brief."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={6}
            data-testid="job-brief"
            placeholder="Recording studio in Lagos. Clients book sessions. We invoice in naira. Contacts CSV attached."
          />
          <div>
            <label className="block text-sm font-medium text-ink" htmlFor="job-files">
              Client files
            </label>
            <input
              id="job-files"
              type="file"
              multiple
              className="mt-1 block w-full text-sm text-ink"
              onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            />
            {files.length ? (
              <p className="mt-1 text-xs text-muted">{files.length} file(s) selected</p>
            ) : (
              <p className="mt-1 text-xs text-muted">CSV, XLSX, or PDF. Optional for packet planning.</p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={busy !== null}
              loading={busy === "packet"}
              onClick={() => void planPacket()}
            >
              Plan packet
            </Button>
            <Button
              type="button"
              disabled={busy !== null || production || observer}
              loading={busy === "run"}
              onClick={() => void runJob()}
            >
              Run Autopilot
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <div className="space-y-3 p-4">
          <h2 className="font-[family-name:var(--font-display)] text-lg text-ink">Progress</h2>
          {busy ? (
            <div
              className="flex flex-col items-center gap-2 py-4"
              data-testid="job-autopilot-progress"
            >
              <InfinityLoop aria-hidden />
              <p className="text-sm text-muted">
                {busy === "run"
                  ? "Running Autopilot…"
                  : busy === "packet"
                    ? "Planning packet…"
                    : "Working…"}
              </p>
            </div>
          ) : null}
          <ol className="flex flex-wrap gap-2">
            {STAGES.map((id) => (
              <li key={id}>
                <Badge variant={stageDone(stages, id) ? "success" : "default"}>{id}</Badge>
              </li>
            ))}
          </ol>
          {result?.connection_kind ? (
            <p className="text-xs text-muted">
              Connection: {result.connection_kind}
              {result.sandbox ? " (unattended sandbox)" : ""}
            </p>
          ) : packetOut ? (
            <p className="text-xs text-muted">
              Connection: {packetOut.connection_kind}
              {packetOut.sandbox ? " (sandbox)" : " — run will need confirm"}
            </p>
          ) : null}
        </div>
      </Card>

      {packet ? (
        <Card>
          <div className="space-y-3 p-4">
            <h2 className="font-[family-name:var(--font-display)] text-lg text-ink">Job packet</h2>
            {packet.structured_brief ? (
              <pre
                className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-surface-muted p-3 text-xs text-ink"
                data-testid="job-structured-brief"
              >
                {packet.structured_brief}
              </pre>
            ) : null}
            <p className="text-sm text-ink">
              Domain: {packet.domain_label}
              {packet.country_code ? ` · ${packet.country_code}` : ""}
              {packet.currency ? ` · ${packet.currency}` : ""}
              {packet.l10n_module ? ` · ${packet.l10n_module}` : ""}
            </p>
            <p className="text-sm">
              <span className="font-medium">Stock apps:</span>{" "}
              {packet.stock_apps.join(", ") || "(none)"}
            </p>
            <p className="text-sm">
              <span className="font-medium">Connectors:</span>{" "}
              {packet.connectors?.length
                ? packet.connectors.join(" → ")
                : "none detected"}
            </p>
            <p className="text-sm">
              <span className="font-medium">Custom residual:</span>{" "}
              {packet.custom_residuals.length
                ? packet.custom_residuals.map((r) => `${r.model} (${r.key})`).join(", ")
                : "none — stock + data only"}
            </p>
            {packet.data_files.length ? (
              <p className="text-sm">
                <span className="font-medium">Files:</span>{" "}
                {packet.data_files.map((f) => `${f.filename}→${f.doc_type}`).join(", ")}
              </p>
            ) : null}
            {packet.grounding?.length ? (
              <p className="text-sm">
                <span className="font-medium">Client-doc grounding:</span>{" "}
                {packet.grounding.length} chunk(s)
              </p>
            ) : null}
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
              {packet.decision_record.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          </div>
        </Card>
      ) : null}

      {result?.bootstrap ? (
        <Card>
          <div className="space-y-2 p-4 text-sm">
            <h2 className="font-[family-name:var(--font-display)] text-lg text-ink">Stock bootstrap</h2>
            <p>{result.bootstrap.message}</p>
            {result.bootstrap.installed.length ? (
              <p>Installed: {result.bootstrap.installed.join(", ")}</p>
            ) : null}
            {result.bootstrap.skipped.length ? (
              <p>
                Skipped: {result.bootstrap.skipped.join(", ")}
              </p>
            ) : null}
            {result.bootstrap.warnings.length ? (
              <ul className="list-disc space-y-1 pl-5 text-sm text-amber-800">
                {result.bootstrap.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            ) : null}
            {result.bootstrap.probes.map((p, i) => (
              <p key={`${p.name}-${i}`}>
                <Badge variant={p.ok ? "success" : "warning"}>{p.name}</Badge> {p.detail}
              </p>
            ))}
          </div>
        </Card>
      ) : null}

      {result?.connectors && !result.connectors.skipped ? (
        <Card>
          <div className="space-y-2 p-4 text-sm">
            <h2 className="font-[family-name:var(--font-display)] text-lg text-ink">
              Connectors (domain-agnostic)
            </h2>
            <p>{result.connectors.message}</p>
            {result.connectors.ran.length ? (
              <p>Ran: {result.connectors.ran.join(", ")}</p>
            ) : null}
            {result.connectors.skipped_ids?.length ? (
              <p>Skipped: {result.connectors.skipped_ids.join(", ")}</p>
            ) : null}
            {result.connectors.failed.length ? (
              <p>Gaps: {result.connectors.failed.join(", ")}</p>
            ) : null}
            {result.connectors.steps.map((p, i) => (
              <p key={`${p.name}-${i}`}>
                <Badge variant={p.ok ? "success" : "warning"}>{p.name}</Badge> {p.detail}
              </p>
            ))}
          </div>
        </Card>
      ) : null}

      {result?.custom ? (
        <Card>
          <div className="space-y-2 p-4 text-sm">
            <h2 className="font-[family-name:var(--font-display)] text-lg text-ink">Custom residual</h2>
            <p>
              {result.custom.skipped
                ? result.custom.reason || "Skipped."
                : result.custom.apply_message || "Applied."}
            </p>
            {result.custom.fields_relaxed ? (
              <p>Relaxed {result.custom.fields_relaxed} leftover required field(s).</p>
            ) : null}
            {result.custom.expert_score_after != null ? (
              <p>
                Expert-fix {result.custom.expert_score_before ?? "?"} → {result.custom.expert_score_after}
              </p>
            ) : null}
          </div>
        </Card>
      ) : null}

      {result?.ingest && !result.ingest.skipped ? (
        <Card>
          <div className="space-y-2 p-4 text-sm">
            <h2 className="font-[family-name:var(--font-display)] text-lg text-ink">Data</h2>
            <p>{result.ingest.message}</p>
            {result.ingest.source_rows || result.ingest.loaded_rows ? (
              <p>
                Rows: {result.ingest.loaded_rows ?? 0}/{result.ingest.source_rows ?? 0}
                {result.ingest.unmatched_m2o?.length
                  ? ` · unmatched M2O ${result.ingest.unmatched_m2o.length}`
                  : ""}
              </p>
            ) : null}
            {result.ingest.gaps.length ? (
              <ul className="list-disc pl-5">
                {result.ingest.gaps.map((g) => (
                  <li key={g}>{g}</li>
                ))}
              </ul>
            ) : null}
          </div>
        </Card>
      ) : null}

      {result?.job_scorecard ? (
        <Card>
          <div className="space-y-2 p-4 text-sm">
            <h2 className="font-[family-name:var(--font-display)] text-lg text-ink">
              Implementation-job scorecard
            </h2>
            <p className="text-xs text-muted">{result.job_scorecard.modulespec_completeness_note}</p>
            <p>
              overall {result.job_scorecard.overall.toFixed(1)} · stack {result.job_scorecard.stack_fit.toFixed(1)} ·
              coverage {result.job_scorecard.stock_coverage.toFixed(1)} · data {result.job_scorecard.data_load.toFixed(1)} ·
              smoke {result.job_scorecard.process_smoke.toFixed(1)}
            </p>
            {typeof result.retry_count === "number" && result.retry_count > 0 ? (
              <p>Retries: {result.retry_count}</p>
            ) : null}
            <ul className="list-disc space-y-1 pl-5 text-muted">
              {result.job_scorecard.findings.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </div>
        </Card>
      ) : null}

      {result?.smoke ? (
        <Card>
          <div className="space-y-2 p-4 text-sm">
            <h2 className="font-[family-name:var(--font-display)] text-lg text-ink">Process smoke</h2>
            <p>
              <Badge variant={result.smoke.ok ? "success" : "danger"}>
              {result.smoke.ok ? "passed" : "failed"}
            </Badge>{" "}
            {result.smoke.named_process ? `${result.smoke.named_process} · ` : ""}
            {result.smoke.message}
            </p>
            {result.smoke.steps.map((s) => (
              <p key={s.name}>
                {s.ok ? "ok" : "fail"} · {s.name}: {s.detail}
              </p>
            ))}
          </div>
        </Card>
      ) : null}

      <Card>
        <div className="space-y-3 p-4 text-sm">
          <h2 className="font-[family-name:var(--font-display)] text-lg text-ink">
            Config Packet — client replay
          </h2>
          <p className="text-muted">
            Autopilot never writes production. After sandbox smoke, fingerprint the client,
            dry-run the delta, then apply with the confirm phrase. SMTP and payment keys stay
            a paste-in-Odoo checklist.
          </p>
          {configPacket ? (
            <>
              <p>
                sha256 {configPacket.sha256} · recipe v{configPacket.recipe_version} ·{" "}
                {configPacket.modules.length} module(s) · {configPacket.users.length} user(s)
              </p>
              <ul className="list-disc space-y-1 pl-5">
                {(configDiff?.checklist || configPacket.checklist).map((item) => (
                  <li key={item.id}>
                    <Badge
                      variant={
                        item.status === "done"
                          ? "success"
                          : item.status === "blocked"
                            ? "danger"
                            : item.status === "secret"
                              ? "warning"
                              : "default"
                      }
                    >
                      {item.status}
                    </Badge>{" "}
                    {item.label}
                    {(() => {
                      const href = checklistOpenHref(item, connection?.url);
                      if (href) {
                        return (
                          <a
                            href={href}
                            target="_blank"
                            rel="noreferrer"
                            className="ml-2 text-xs text-accent hover:underline"
                          >
                            Open in Odoo
                          </a>
                        );
                      }
                      if (item.href_hint) {
                        return <span className="block text-xs text-muted">{item.href_hint}</span>;
                      }
                      return null;
                    })()}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-muted">Run Autopilot on the sandbox to emit a packet.</p>
          )}
          {fingerprint ? (
            <p className="text-xs text-muted">
              Fingerprint {fingerprint.sha256}: {fingerprint.modules_installed.length} installed
              apps, {fingerprint.account_code_count} CoA codes, {fingerprint.user_logins.length}{" "}
              users.
            </p>
          ) : null}
          {configDiff ? (
            <p>
              Dry-run: {configDiff.message}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={busy !== null}
              loading={busy === "fingerprint"}
              onClick={() => void runFingerprint()}
            >
              Fingerprint target
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={busy !== null}
              loading={busy === "settings"}
              onClick={() => void captureSettings()}
            >
              Capture Settings
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={busy !== null || !configPacket}
              loading={busy === "dryrun"}
              onClick={() => void runConfigDryRun()}
            >
              Dry-run packet
            </Button>
            <Button
              type="button"
              disabled={busy !== null || !configPacket}
              onClick={() => setApplyPacketOpen(true)}
            >
              Apply packet to target
            </Button>
            <Button type="button" variant="ghost" disabled={!configPacket} onClick={downloadConfigPacket}>
              Download packet JSON
            </Button>
          </div>
        </div>
      </Card>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm text-ink">
          Promote target
          <select
            className="mt-1 block min-w-[16rem] rounded border border-line bg-white px-2 py-1 text-sm"
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
          >
            <option value="">Select another connection…</option>
            {targets.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.write_mode})
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        {sandboxUrl ? (
          <Button asChild>
            <a href={sandboxUrl} target="_blank" rel="noreferrer">
              {sandboxLabel}
            </a>
          </Button>
        ) : null}
        <Button
          type="button"
          variant="secondary"
          disabled={!result?.promote_ready || busy !== null}
          onClick={() => setPromoteOpen(true)}
        >
          {residualZipBase64(result) ? "Promote to target" : "Handoff"}
        </Button>
        <Button type="button" variant="ghost" disabled={!result} onClick={downloadReport}>
          Download markdown
        </Button>
        <Button
          type="button"
          variant="ghost"
          disabled={!result || busy !== null}
          loading={busy === "pdf"}
          onClick={() => void downloadPdf()}
        >
          Download PDF
        </Button>
        <Button asChild variant="ghost">
          <Link href={`/connections/${connectionId}/wizard`}>Draft Studio</Link>
        </Button>
      </div>

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
    </div>
  );
}
