"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { CodeEditorPanel } from "@/components/CodeEditorPanel";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { Select } from "@/components/ui/Select";
import { api, ConfirmationRequiredError, Connection } from "@/lib/api";
import { reportApiError } from "@/lib/api-error";
import { pollJob } from "@/lib/jobs";
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";

const CONFIRM_PHRASE = "I understand the risks";

type SavedScript = {
  id: string;
  name: string;
  description: string | null;
  script_content: string;
  shared: boolean;
};

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
  const [runs, setRuns] = useState<
    Array<{
      id: string;
      status: string;
      stdout: string | null;
      stderr: string | null;
      write_counts: Record<string, unknown>;
      script_content: string;
    }>
  >([]);
  const [consoleOut, setConsoleOut] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmRisks, setConfirmRisks] = useState<string[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

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
  }, [connectionId]);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  async function abortRun() {
    if (!activeJobId) return;
    setBusy(true);
    setError(null);
    try {
      await api.cancelJob(activeJobId);
      setConsoleOut((prev) => `${prev}\n\n[Aborted job ${activeJobId}]`);
    } catch (err) {
      setError(reportApiError(err));
    } finally {
      setBusy(false);
      setActiveJobId(null);
      await refresh();
    }
  }

  async function saveCurrentScript() {
    if (!saveName.trim()) {
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
      await refresh();
    } catch (err) {
      setError(reportApiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function executeRun() {
    setBusy(true);
    setError(null);
    setConsoleOut("");
    try {
      const res = await api.runScript(connectionId, {
        script,
        async_job: true,
        count_writes: true,
        confirm_advanced: true,
        confirm_phrase: CONFIRM_PHRASE,
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
          | { stdout?: string; stderr?: string; write_counts?: Record<string, unknown> }
          | undefined;
        setConsoleOut(
          `${result?.stdout ?? ""}${result?.stderr ? `\n${result.stderr}` : ""}\n\nWrite counts: ${JSON.stringify(result?.write_counts ?? {}, null, 2)}`,
        );
      }
      await refresh();
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmRisks(err.risks);
        setConfirmOpen(true);
      } else {
        setError(reportApiError(err));
      }
    } finally {
      setBusy(false);
      setActiveJobId(null);
    }
  }

  return (
    <div className="space-y-6" data-testid="script-runner-page">
      <PageHeader
        title="Script Runner"
        description="Ad-hoc Python against this connection via typed RPC — isolated subprocess, journaled with full script content."
      />
      {error ? <ErrorNotice message={error} /> : null}
      {connection ? <FirstWriteInterstitial connection={connection} /> : null}
      {connection?.write_mode === "observer" ? (
        <Callout variant="warning" title="Observer mode">
          Unlock write mode before running scripts that mutate Odoo.
        </Callout>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2 space-y-4 p-4">
          <div className="flex flex-wrap gap-2">
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
            <Button onClick={() => executeRun()} disabled={busy || Boolean(activeJobId)}>
              {busy ? "Running…" : "Run script"}
            </Button>
            {activeJobId ? (
              <Button variant="secondary" onClick={abortRun} disabled={!activeJobId} data-testid="script-runner-abort">
                Abort
              </Button>
            ) : null}
          </div>
          <CodeEditorPanel
            value={script}
            onChange={setScript}
            label="Script"
            rows={18}
            testId="script-runner-editor"
          />
          <div className="flex flex-wrap items-end gap-2">
            <Input
              label="Save as"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              placeholder="My batch script"
            />
            <Button variant="secondary" size="sm" onClick={saveCurrentScript} disabled={busy}>
              Save to library
            </Button>
          </div>
          <Card className="bg-surface-muted p-3">
            <h3 className="text-sm font-semibold">Console</h3>
            <pre
              className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-mono text-xs"
              data-testid="script-runner-console"
            >
              {consoleOut || "(output appears here)"}
            </pre>
          </Card>
        </Card>

        <div className="space-y-4">
          <Card className="p-4 space-y-3">
            <h2 className="text-sm font-semibold">Saved scripts</h2>
            {savedScripts.length === 0 ? (
              <p className="text-xs text-muted">No saved scripts yet.</p>
            ) : (
              <ul className="space-y-2 text-xs" data-testid="script-runner-library">
                {savedScripts.map((s) => (
                  <li key={s.id} className="border-b border-border-subtle pb-2">
                    <button
                      type="button"
                      className="font-medium text-accent hover:underline"
                      onClick={() => setScript(s.script_content)}
                    >
                      {s.name}
                    </button>
                    {s.description ? <p className="text-muted">{s.description}</p> : null}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="p-4 space-y-3">
            <h2 className="text-sm font-semibold">Run history</h2>
            <ul className="space-y-2 text-xs">
              {runs.map((r) => (
                <li key={r.id} className="border-b border-border-subtle pb-2">
                  <span className="font-mono text-accent">{r.status}</span> · {r.id.slice(0, 8)}
                  {Object.keys(r.write_counts || {}).length ? (
                    <p className="text-muted">writes: {JSON.stringify(r.write_counts)}</p>
                  ) : null}
                  <pre className="mt-1 max-h-20 overflow-auto whitespace-pre-wrap text-muted">
                    {r.script_content.slice(0, 200)}
                  </pre>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>

      <ConfirmDialogV2
        open={confirmOpen}
        title="Run script"
        warning="Script Runner executes Python with your Odoo credentials."
        risks={confirmRisks.length ? confirmRisks : ["Uses real RPC against this connection"]}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => executeRun()}
        busy={busy}
        riskLevel="danger"
      />
    </div>
  );
}
