"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { toast } from "sonner";
import { PythonLineEditor, type LineDiagnostic } from "@/components/code-studio/PythonLineEditor";
import { ScriptRunnerErrorNotice } from "@/components/script-runner/ScriptRunnerErrorNotice";
import { OperateStudioBar } from "@/components/operate-studio/OperateStudioBar";
import { ScriptRunnerStageRail } from "@/components/script-runner/ScriptRunnerStageRail";
import { ScriptRunnerStateGuide } from "@/components/script-runner/ScriptRunnerStateGuide";
import "@/components/script-runner/script-runner-operate.css";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { DURATION, EASE_ENTER_EXIT, seconds } from "@/components/ui/motion/constants";
import { Select } from "@/components/ui/Select";
import { api, ConfirmationRequiredError, Connection } from "@/lib/api";
import { reportApiError } from "@/lib/api-error";
import { pollJob } from "@/lib/jobs";
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";
import {
  CONFIRM_PHRASE,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  RESTORE_NOTE,
  SANDBOX_LIMITS,
  emptyScriptRunnerGuide,
  failedScriptRunnerGuide,
  idleScriptRunnerGuide,
  observerScriptRunnerGuide,
  resultHonestyLabel,
  sanitizeScriptRunnerCopy,
  scriptRunnerHonestyGuide,
  scriptRunnerSessionBadge,
  scriptRunnerStepFromState,
  succeededScriptRunnerGuide,
} from "@/lib/scriptRunnerScreen";
import { FrameMeta } from "@/components/frame/FrameMeta";

type SavedScript = {
  id: string;
  name: string;
  description: string | null;
  script_content: string;
  shared: boolean;
};

type ScriptRunRow = {
  id: string;
  status: string;
  script_hash?: string;
  stdout: string | null;
  stderr: string | null;
  write_counts: Record<string, unknown>;
  write_count?: number;
  error: string | null;
  snapshot_id?: string | null;
  script_content: string;
};

type ErrorContext = "load" | "save" | "run" | "abort" | "observer";

function ResultMotion({ children }: { children: React.ReactNode }) {
  const reduced = useReducedMotion() ?? false;
  return (
    <motion.div
      initial={reduced ? { opacity: 0 } : { opacity: 0, y: 4 }}
      animate={reduced ? { opacity: 1 } : { opacity: 1, y: 0 }}
      transition={{
        duration: seconds(reduced ? DURATION.reducedMotionMs : DURATION.dropdownMs),
        ease: [...EASE_ENTER_EXIT.bezier],
      }}
    >
      {children}
    </motion.div>
  );
}

function scriptDiagnostics(source: string): LineDiagnostic[] {
  const found: LineDiagnostic[] = [];
  source.split("\n").forEach((line, index) => {
    if (/\b(import|from)\s+(os|socket|urllib|http|pathlib|subprocess|shutil|ssl)\b/.test(line)) {
      found.push({
        line: index + 1,
        message: "That import is not available. The script stays inside the allowlist.",
      });
    }
    if (/res\.users/.test(line) && /unlink/.test(line)) {
      found.push({ line: index + 1, message: "Unlink on res.users is refused." });
    }
    if (/database\.(secret|uuid|create_date|enterprise_code|expiration_date)|web\.base\.url/.test(line)) {
      found.push({ line: index + 1, message: "That database parameter is protected." });
    }
  });
  return found;
}

function statusLabel(status: string): string {
  if (status === "succeeded") return "Succeeded";
  if (status === "failed") return "Failed";
  if (status === "queued") return "Queued";
  if (status === "running") return "Running";
  return status;
}

function failureSummary(error: string): string {
  const lines = error
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const concrete = lines.find((line) => !line.startsWith("Traceback") && !line.startsWith("File "));
  return (concrete || lines[0] || "The script failed.").slice(0, 400);
}

export default function ScriptRunnerPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [script, setScript] = useState("log('Hello from Script Runner')\n");
  const [templates, setTemplates] = useState<
    Array<{ id: string; label: string; description: string; code: string }>
  >([]);
  const [savedScripts, setSavedScripts] = useState<SavedScript[]>([]);
  const [saveName, setSaveName] = useState("");
  const [runs, setRuns] = useState<ScriptRunRow[]>([]);
  const [consoleOut, setConsoleOut] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorContext, setErrorContext] = useState<ErrorContext>("load");
  const [succeeded, setSucceeded] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmRisks, setConfirmRisks] = useState<string[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [sidebarHydrated, setSidebarHydrated] = useState(false);

  const diagnostics = useMemo(() => scriptDiagnostics(script), [script]);
  const lastRun = runs[0] ?? null;
  const isObserver = connection?.write_mode === "observer";

  const stage = scriptRunnerStepFromState({
    hasScript: Boolean(script.trim()),
    confirmOpen,
    busy: busy || Boolean(activeJobId),
    hasResult: Boolean(lastRun) || succeeded,
  });

  const refresh = useCallback(async () => {
    const [conn, tpl, history, library] = await Promise.all([
      api.getConnection(connectionId),
      api.getScriptRunnerTemplates(connectionId),
      api.listScriptRuns(connectionId),
      api.listSavedScripts(connectionId).catch(() => []),
    ]);
    setConnection(conn);
    setTemplates(tpl.templates);
    setRuns(history);
    setSavedScripts(library);
    return history;
  }, [connectionId]);

  useEffect(() => {
    setSidebarHydrated(false);
    refresh()
      .catch((err: Error) => {
        setErrorContext("load");
        setError(err.message);
      })
      .finally(() => setSidebarHydrated(true));
  }, [refresh]);

  function openConfirm() {
    setConfirmRisks([
      "There is no test run. After you confirm, the script uses real Odoo RPC",
      "Runs in an isolated subprocess but uses this connection's credentials",
      "Write counts are reported but side effects are not auto-reversed",
      "Unlink on users, companies, XML ids, and protected database parameters is refused",
    ]);
    setConfirmOpen(true);
  }

  async function abortRun() {
    if (!activeJobId) return;
    setBusy(true);
    setError(null);
    setSucceeded(false);
    try {
      await api.cancelJob(activeJobId);
      setConsoleOut((prev) => `${prev}\n\n[Aborted job ${activeJobId}]`);
      toast.message("Run aborted", { description: "The script process was stopped." });
    } catch (err) {
      setErrorContext("abort");
      setError(reportApiError(err));
    } finally {
      setBusy(false);
      setActiveJobId(null);
      await refresh();
    }
  }

  async function saveCurrentScript() {
    if (!saveName.trim()) {
      setErrorContext("save");
      setError("Enter a name to save this script.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.saveScript(connectionId, {
        name: saveName.trim(),
        script_content: script,
        shared: true,
      });
      setSaveName("");
      toast.success("Script saved", { description: "It is in the library for this connection." });
      await refresh();
    } catch (err) {
      setErrorContext("save");
      setError(reportApiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function executeRun(phrase: string) {
    setBusy(true);
    setError(null);
    setSucceeded(false);
    setConsoleOut("");
    try {
      const res = await api.runScript(connectionId, {
        script,
        async_job: true,
        count_writes: true,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      if (res.job_id) {
        setActiveJobId(res.job_id);
        const job = await pollJob(res.job_id, {
          fetchJob: api.getJob,
          onUpdate: (j) => {
            const partial = j.result as { stdout?: string; stderr?: string } | undefined;
            if (partial?.stdout || partial?.stderr) {
              setConsoleOut(`${partial.stdout ?? ""}${partial.stderr ?? ""}`);
            }
          },
        });
        const result = job.result as
          | { stdout?: string; stderr?: string; write_counts?: Record<string, unknown>; error?: string }
          | undefined;
        setConsoleOut(
          `${result?.stdout ?? ""}${result?.stderr ? `\n${result.stderr}` : ""}\n\nWrite counts: ${JSON.stringify(result?.write_counts ?? {}, null, 2)}`,
        );
      }
      const history = await refresh();
      const latest = history[0];
      if (latest?.status === "failed") {
        const summary = failureSummary(latest.error || "The script failed.");
        setErrorContext("run");
        setError(summary);
        toast.error("Script failed", { description: summary });
      } else if (latest?.status === "succeeded") {
        setSucceeded(true);
        toast.success("Script finished", {
          description: `${latest.write_count ?? 0} writes recorded.`,
        });
      }
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmRisks(err.risks);
        setConfirmOpen(true);
      } else {
        setErrorContext("run");
        setError(reportApiError(err));
        await refresh().catch(() => undefined);
      }
    } finally {
      setBusy(false);
      setActiveJobId(null);
    }
  }

  return (
    <div
      className="script-runner-operate op-studio-shell space-y-0 p-4 sm:p-6"
      data-testid="script-runner-page"
      aria-busy={busy}
    >
      <header className="op-studio" data-testid="script-runner-studio-chrome">
        <div className="op-titlebar">
          <div className="op-title-block">
            <FrameMeta />
            <p className="op-kicker">{connection?.name ?? connectionId}</p>
            <h1 className="op-title">{PAGE_TITLE}</h1>
            <p className="op-subtitle">{PAGE_DESCRIPTION}</p>
          </div>
        </div>
        <OperateStudioBar
          testIdPrefix="script-runner"
          badge={scriptRunnerSessionBadge(stage)}
          honesty={
            lastRun?.status === "succeeded" || lastRun?.status === "failed"
              ? null
              : scriptRunnerHonestyGuide()
          }
          hint={
            lastRun?.status === "succeeded"
              ? "Last run succeeded. Snapshot restore is only partly recoverable."
              : "Last run failed. Fix the error, then Run script again."
          }
          sanitize={sanitizeScriptRunnerCopy}
        />
        <ScriptRunnerStageRail step={stage} />
      </header>

      <div className="op-desk">
        <div className="op-paper space-y-4">
      <div className="sr-limits" data-testid="script-runner-limits">
        <h2 className="sr-limits-title">What this run can do</h2>
        <p className="sr-limits-body">{SANDBOX_LIMITS}</p>
      </div>

      {error ? (
        <ScriptRunnerErrorNotice
          message={error}
          context={errorContext}
          onRetry={() =>
            refresh().catch((err: Error) => {
              setErrorContext("load");
              setError(err.message);
            })
          }
          onDismiss={() => setError(null)}
        />
      ) : null}

      {succeeded && lastRun?.status === "succeeded" ? (
        <ResultMotion>
          <ScriptRunnerStateGuide
            tone="success"
            testId="script-runner-success"
            guide={succeededScriptRunnerGuide({
              writeCount: lastRun.write_count ?? 0,
              snapshotId: lastRun.snapshot_id,
            })}
          />
        </ResultMotion>
      ) : null}

      {connection ? <FirstWriteInterstitial connection={connection} /> : null}

      {isObserver ? (
        <ScriptRunnerStateGuide
          tone="warning"
          testId="script-runner-observer"
          guide={observerScriptRunnerGuide()}
        />
      ) : null}

      {!sidebarHydrated ? null : !lastRun && !error && !isObserver ? (
        <ScriptRunnerStateGuide
          density="brief"
          testId="script-runner-idle-guide"
          guide={idleScriptRunnerGuide()}
        />
      ) : null}

      {busy || activeJobId ? (
        <div className="sr-progress" aria-busy="true" data-testid="script-runner-progress" aria-live="polite">
          Running the script. Output appears when the run finishes.
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="sr-panel space-y-4 lg:col-span-2" data-testid="script-runner-editor-panel">
          <div>
            <h2 className="sr-panel-title">Script</h2>
            <p className="sr-panel-sub">
              Compose Python for this connection. Line warnings mark imports and RPCs the sandbox refuses.
            </p>
          </div>
          <div className="sr-actions">
            <Select
              value=""
              onChange={(e) => {
                const t = templates.find((x) => x.id === e.target.value);
                if (t) setScript(t.code);
              }}
              aria-label="Load template"
              placeholder="Load template…"
              options={templates.map((t) => ({ value: t.id, label: t.label }))}
            />
            <Select
              value=""
              onChange={(e) => {
                const s = savedScripts.find((x) => x.id === e.target.value);
                if (s) setScript(s.script_content);
              }}
              aria-label="Load saved script"
              data-testid="script-runner-saved-select"
              placeholder="Load saved script…"
              options={savedScripts.map((s) => ({ value: s.id, label: s.name }))}
            />
            <Button
              variant="primary"
              onClick={openConfirm}
              disabled={busy || Boolean(activeJobId) || isObserver}
              data-testid="script-runner-run-btn"
            >
              {busy ? "Running…" : PRIMARY_CTA}
            </Button>
            {activeJobId ? (
              <Button
                variant="secondary"
                onClick={abortRun}
                disabled={!activeJobId}
                data-testid="script-runner-abort"
              >
                Abort
              </Button>
            ) : null}
          </div>
          <PythonLineEditor
            value={script}
            onChange={setScript}
            label="Script"
            diagnostics={diagnostics}
            testId="script-runner-editor"
          />
          <div className="flex flex-wrap items-end gap-2">
            <Input
              id="script-runner-save-name"
              label="Save as"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              placeholder="My batch script"
            />
            <Button variant="secondary" size="sm" onClick={saveCurrentScript} disabled={busy}>
              Save to library
            </Button>
          </div>
          <div className="sr-console">
            <h3 className="sr-console-title">Console</h3>
            <pre
              className="sr-console-pre"
              data-testid="script-runner-console"
              aria-live="polite"
            >
              {busy
                ? "Running the script. Output appears when the run finishes."
                : consoleOut || "Output appears here after a run."}
            </pre>
          </div>
        </section>

        <div className="space-y-4">
          <section className="sr-panel space-y-3" data-testid="script-runner-last-run">
            <h2 className="sr-panel-title">Last run</h2>
            {!sidebarHydrated ? (
              <div className="space-y-2" data-testid="script-runner-last-loading" aria-busy="true">
                <Skeleton className="h-14 w-full" />
                <p className="text-sm text-muted">Loading the last run.</p>
              </div>
            ) : !lastRun ? (
              <EmptyState
                title={emptyScriptRunnerGuide().title}
                description={`${emptyScriptRunnerGuide().why} ${emptyScriptRunnerGuide().next}`}
                action={
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={openConfirm}
                    disabled={busy || isObserver}
                  >
                    {PRIMARY_CTA}
                  </Button>
                }
              />
            ) : (
              <ResultMotion>
                <div className="space-y-2 text-sm">
                  <p className="sr-result-label" data-testid="script-runner-result-label">
                    {resultHonestyLabel(lastRun.status === "succeeded")}
                  </p>
                  <p>
                    <span className="font-medium text-ink">{statusLabel(lastRun.status)}</span>
                    <span className="text-muted"> · {lastRun.write_count ?? 0} writes</span>
                  </p>
                  {lastRun.script_hash ? (
                    <p className="sr-mono">Hash {lastRun.script_hash.slice(0, 12)}</p>
                  ) : null}
                  {lastRun.status === "failed" ? (
                    <ScriptRunnerStateGuide
                      tone="danger"
                      live
                      testId="script-runner-failure"
                      guide={failedScriptRunnerGuide(lastRun.error || "The script failed.")}
                    />
                  ) : null}
                  {lastRun.snapshot_id ? (
                    <div className="space-y-2" data-testid="script-runner-restore">
                      <p className="text-sm text-ink">
                        Snapshot {lastRun.snapshot_id} was taken before this write. {RESTORE_NOTE}
                      </p>
                      <Link
                        href={`/connections/${connectionId}/journal`}
                        className="inline-flex min-h-10 items-center text-sm font-medium text-accent underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                      >
                        Open the journal
                      </Link>
                    </div>
                  ) : null}
                </div>
              </ResultMotion>
            )}
          </section>

          <section className="sr-panel space-y-3" data-testid="script-runner-library-panel">
            <h2 className="sr-panel-title">Saved scripts</h2>
            {!sidebarHydrated ? (
              <div className="space-y-2" data-testid="script-runner-library-loading">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <p className="text-sm text-muted">Loading saved scripts.</p>
              </div>
            ) : savedScripts.length === 0 ? (
              <EmptyState
                title="No saved scripts yet"
                description="Name the script in Save as and store it here for reuse on this connection."
                action={
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => document.getElementById("script-runner-save-name")?.focus()}
                  >
                    Name a script
                  </Button>
                }
              />
            ) : (
              <ul className="space-y-2 text-xs" data-testid="script-runner-library">
                {savedScripts.map((s) => (
                  <li key={s.id} className="sr-history-item">
                    <button
                      type="button"
                      className="sr-library-btn"
                      onClick={() => setScript(s.script_content)}
                    >
                      {s.name}
                    </button>
                    {s.description ? <p className="text-muted">{s.description}</p> : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="sr-panel space-y-3" data-testid="script-runner-history-panel">
            <h2 className="sr-panel-title">Run history</h2>
            {!sidebarHydrated ? (
              <div className="space-y-2" data-testid="script-runner-history-loading">
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
                <p className="text-sm text-muted">Loading run history.</p>
              </div>
            ) : runs.length === 0 ? (
              <EmptyState
                title="No runs logged yet"
                description="Each run adds a new journal row with the script hash, write count, and outcome."
                action={
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={openConfirm}
                    disabled={busy || isObserver}
                  >
                    {PRIMARY_CTA}
                  </Button>
                }
              />
            ) : (
              <ul className="space-y-2 text-xs">
                {runs.map((r) => (
                  <li key={r.id} className="sr-history-item">
                    <span className="font-medium text-ink">{statusLabel(r.status)}</span>
                    <span className="text-muted"> · {r.id.slice(0, 8)}</span>
                    <p className="text-muted">{r.write_count ?? 0} writes</p>
                    <pre className="mt-1 max-h-20 overflow-auto whitespace-pre-wrap text-muted">
                      {r.script_content.slice(0, 200)}
                    </pre>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
        </div>
      </div>

      <ConfirmDialogV2
        open={confirmOpen}
        title="Run script"
        warning="There is no test run. This runs your Python with this connection's Odoo credentials. A write is journaled after you confirm."
        risks={
          confirmRisks.length
            ? confirmRisks
            : ["Uses real RPC against this connection"]
        }
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => {
          void executeRun(phrase);
        }}
        busy={busy}
        riskLevel="danger"
        snapshotNote="A snapshot is saved before a write. Record writes are only partly recoverable."
        phrase={CONFIRM_PHRASE}
      />
    </div>
  );
}
