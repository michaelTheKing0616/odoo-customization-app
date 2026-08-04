"use client";

/**
 * Code Studio editor — lightweight textarea + server-side validation (DEV-1).
 * Chose textarea over CodeMirror/Monaco to avoid ~200KB bundle; Python highlighting
 * via validate panel + optional Expert draft; diagnostics hooks live on POST /validate.
 */

import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import { CodeEditorPanel } from "@/components/CodeEditorPanel";
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";
import { GatingCallout } from "@/components/GatingCallout";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { useShellOptional } from "@/context/ShellContext";
import {
  api,
  CodeStudioGateResponse,
  CodeStudioTestRunResult,
  ConfirmationRequiredError,
  Connection,
  ModelRow,
} from "@/lib/api";
import { reportApiError } from "@/lib/api-error";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";

const CONFIRM_PHRASE = "I understand the risks";

const BIND_KINDS = [
  { value: "standalone", label: "Standalone server action" },
  { value: "model_button", label: "Model action button" },
  { value: "automation", label: "Automation code step" },
] as const;

const TRIGGERS = [
  { value: "on_create", label: "On create" },
  { value: "on_write", label: "On update" },
  { value: "on_create_or_write", label: "On create and edit" },
] as const;

export default function CodeStudioPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const shell = useShellOptional();

  const [connection, setConnection] = useState<Connection | null>(null);
  const [gate, setGate] = useState<CodeStudioGateResponse | null>(null);
  const [models, setModels] = useState<ModelRow[]>([]);
  const [symbols, setSymbols] = useState<{ name: string; description: string }[]>([]);
  const [snippets, setSnippets] = useState<{ id: string; label: string; code: string }[]>([]);
  const [code, setCode] = useState(
    "for rec in records:\n    rec.write({'name': rec.name or 'Updated'})",
  );
  const [name, setName] = useState("Custom code action");
  const [model, setModel] = useState("res.partner");
  const [recordId, setRecordId] = useState("");
  const [bindKind, setBindKind] = useState<(typeof BIND_KINDS)[number]["value"]>("model_button");
  const [trigger, setTrigger] = useState("on_write");
  const [validation, setValidation] = useState<Awaited<
    ReturnType<typeof api.validateCodeStudio>
  > | null>(null);
  const [testResult, setTestResult] = useState<CodeStudioTestRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmRisks, setConfirmRisks] = useState<string[]>([]);
  const [gatingChoice, setGatingChoice] = useState<null>(null);

  useSyncShellContext({ model, draftSummary: `Code Studio: ${name}` });

  const probeOk = Boolean(gate?.probe && (gate.probe as { supported?: boolean }).supported);

  const refresh = useCallback(async () => {
    const [conn, gateRes, modelRows, ctx, snip] = await Promise.all([
      api.getConnection(connectionId),
      api.getCodeStudioGate(connectionId),
      api.listModels(connectionId),
      api.getCodeStudioContext(connectionId),
      api.getCodeStudioSnippets(connectionId),
    ]);
    setConnection(conn);
    setGate(gateRes);
    setModels(modelRows);
    setSymbols(ctx.symbols);
    setSnippets(snip.snippets);
    if (modelRows.some((m) => m.model === "res.partner")) {
      setModel("res.partner");
    } else if (modelRows[0]) {
      setModel(modelRows[0].model);
    }
  }, [connectionId]);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  async function runValidate() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.validateCodeStudio(connectionId, code);
      setValidation(res);
    } catch (err) {
      setError(reportApiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function runTest() {
    setBusy(true);
    setError(null);
    setTestResult(null);
    try {
      const rid = recordId.trim() ? Number(recordId) : null;
      const res = await api.testRunCodeStudio(connectionId, {
        model,
        record_id: rid,
        code,
      });
      setTestResult(res);
      setValidation(res.validation);
    } catch (err) {
      setError(reportApiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitBind(e?: FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api.bindCodeStudio(connectionId, {
        name,
        model,
        code,
        bind_kind: bindKind,
        bind_to_model: bindKind !== "standalone",
        trigger: bindKind === "automation" ? trigger : null,
        confirm_advanced: true,
        confirm_phrase: CONFIRM_PHRASE,
      });
      setNotice(
        `Bound ${res.bind_kind} — snapshot ${res.snapshot_id ?? "n/a"} · action #${res.server_action_id ?? res.automation_id ?? "?"}`,
      );
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
    }
  }

  async function reprobe() {
    setBusy(true);
    setError(null);
    try {
      await api.probeCodeStudio(connectionId);
      await refresh();
      setNotice("Capability probe refreshed.");
    } catch (err) {
      setError(reportApiError(err));
    } finally {
      setBusy(false);
    }
  }

  const expertDraftQuestion = useMemo(
    () =>
      `Draft a safe_eval server action for model ${model}. Context: records, record, model, env, log, UserError. Return Python only — no imports.`,
    [model],
  );

  return (
    <div className="space-y-6" data-testid="code-studio-page">
      <PageHeader
        title="Code Studio"
        description="Author live state=code server actions where this instance proves RPC support. Test on one record before binding."
      />
      {connection ? <FirstWriteInterstitial connection={connection} /> : null}

      {error ? <ErrorNotice message={error} /> : null}
      {notice ? (
        <Callout variant="info" title="Success">
          {notice}
        </Callout>
      ) : null}

      {gate && !probeOk ? (
        <div className="space-y-3">
          <GatingCallout
            gating={gate.gating}
            selectedChoice={gatingChoice}
            onSelectChoice={() => setGatingChoice(null)}
          />
          <Button variant="secondary" size="sm" onClick={reprobe} disabled={busy}>
            Re-probe instance
          </Button>
        </div>
      ) : null}

      {probeOk ? (
        <>
          <Callout variant="warning" title="Live Python on this database">
            Code runs with your Odoo credentials. Pick a test record; binding requires typing
            &quot;{CONFIRM_PHRASE}&quot; and creates a snapshot.
          </Callout>

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2 space-y-4 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-semibold">Editor</h2>
                <div className="flex flex-wrap gap-2">
                  <ExplainThisButton
                    question={`Explain this Odoo server action code in safe_eval context:\n\n${code}`}
                    label="Explain this code"
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    type="button"
                    onClick={() =>
                      shell?.openExpert({
                        question: expertDraftQuestion,
                      })
                    }
                  >
                    Draft code for me
                  </Button>
                  <Select
                    value=""
                    onChange={(e) => {
                      const sn = snippets.find((s) => s.id === e.target.value);
                      if (sn) setCode(sn.code);
                    }}
                    aria-label="Insert snippet"
                    placeholder="Insert snippet…"
                    options={snippets.map((s) => ({ value: s.id, label: s.label }))}
                  />
                </div>
              </div>
              <CodeEditorPanel
                value={code}
                onChange={setCode}
                label="Python (safe_eval)"
                rows={18}
                testId="code-studio-editor"
              />
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" size="sm" onClick={runValidate} disabled={busy}>
                  Check syntax
                </Button>
                <Button variant="secondary" size="sm" onClick={runTest} disabled={busy}>
                  Test run on record
                </Button>
              </div>
              {validation ? (
                <div className="space-y-2">
                  {!validation.ok ? (
                    <Callout variant="danger" title="Validation failed">
                      {validation.error}
                    </Callout>
                  ) : validation.warnings.length ? (
                    <Callout variant="warning" title="Warnings">
                      <ul className="list-disc pl-5">
                        {validation.warnings.map((w) => (
                          <li key={w.code}>{w.message}</li>
                        ))}
                      </ul>
                    </Callout>
                  ) : (
                    <Callout variant="info" title="Syntax OK">
                      No static warnings.
                    </Callout>
                  )}
                </div>
              ) : null}
              {testResult ? (
                <div className="space-y-2" data-testid="code-studio-test-result">
                  <Callout
                    variant={testResult.ok ? "info" : "danger"}
                    title={
                      testResult.ran_for_real
                        ? "This ran for real on that record"
                        : "Test run"
                    }
                  >
                    {testResult.exception ?? "Completed without exception."}
                  </Callout>
                  {testResult.field_diff.length ? (
                    <CodeBlock
                      language="json"
                      code={JSON.stringify(testResult.field_diff, null, 2)}
                    />
                  ) : (
                    <p className="text-sm text-muted">No scalar field changes detected.</p>
                  )}
                </div>
              ) : null}
            </Card>

            <div className="space-y-4">
              <Card className="p-4 space-y-3">
                <h2 className="text-sm font-semibold">safe_eval context</h2>
                <p className="text-xs text-muted">
                  Odoo {connection?.server_version ?? "?"} — documented server-action symbols.
                </p>
                <ul className="space-y-2 text-sm">
                  {symbols.map((s) => (
                    <li key={s.name}>
                      <code className="font-mono text-accent">{s.name}</code>
                      <span className="text-muted"> — {s.description}</span>
                    </li>
                  ))}
                </ul>
              </Card>

              <Card className="p-4 space-y-3">
                <h2 className="text-sm font-semibold">Bind action</h2>
                <form className="space-y-3" onSubmit={submitBind}>
                  <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} />
                  <Select
                    label="Model"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    options={models.map((m) => ({ value: m.model, label: m.model }))}
                  />
                  <Input
                    label="Test record ID (optional for bind)"
                    value={recordId}
                    onChange={(e) => setRecordId(e.target.value)}
                    placeholder="e.g. 7"
                  />
                  <Select
                    label="Bind as"
                    value={bindKind}
                    onChange={(e) =>
                      setBindKind(e.target.value as (typeof BIND_KINDS)[number]["value"])
                    }
                    options={BIND_KINDS.map((k) => ({ value: k.value, label: k.label }))}
                  />
                  {bindKind === "automation" ? (
                    <Select
                      label="Trigger"
                      value={trigger}
                      onChange={(e) => setTrigger(e.target.value)}
                      options={TRIGGERS.map((t) => ({ value: t.value, label: t.label }))}
                    />
                  ) : null}
                  <Button type="submit" disabled={busy}>
                    Bind with confirm + snapshot
                  </Button>
                </form>
              </Card>
            </div>
          </div>
        </>
      ) : null}

      <ConfirmDialogV2
        open={confirmOpen}
        title="Bind live Python"
        warning="You are binding live Python (state=code) on this database."
        risks={
          confirmRisks.length
            ? confirmRisks
            : ["Runs with Odoo credentials on this connection"]
        }
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => submitBind()}
        busy={busy}
        riskLevel="danger"
        snapshotNote="A snapshot is created before bind."
      />
    </div>
  );
}
