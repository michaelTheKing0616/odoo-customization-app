"use client";

import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { toast } from "sonner";
import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";
import { GatingCallout } from "@/components/GatingCallout";
import { Button } from "@/components/ui/Button";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Check, CircleAlert, Lock } from "@/components/ui/icons";
import { EmptyState, Kbd, Skeleton } from "@/components/ui/layout-primitives";
import { OperateStudioChrome } from "@/components/operate-studio/OperateStudioChrome";
import { DURATION, EASE_ENTER_EXIT, seconds } from "@/components/ui/motion/constants";
import { useShellOptional } from "@/context/ShellContext";
import {
  api,
  CodeStudioGateResponse,
  CodeStudioTestRunResult,
  CodeStudioValidateResult,
  ConfirmationRequiredError,
  Connection,
  ModelRow,
} from "@/lib/api";
import { formatApiError, reportApiError } from "@/lib/api-error";
import { downloadBase64Zip } from "@/components/overview/overview-helpers";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { presentCodeStudioError } from "./present-error";
import { CodeStudioGateRail } from "./CodeStudioGateRail";
import { CodeStudioHonesty } from "./CodeStudioHonesty";
import {
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  codeStudioHonestyGuide,
  codeStudioSessionBadge,
  sanitizeCodeStudioCopy,
} from "@/lib/codeStudioScreen";
import { PythonLineEditor } from "./PythonLineEditor";
import {
  authoringGate,
  diagnosticsFor,
  liveBindGate,
  optionAGate,
  railSteps,
  testRunGate,
  type Pinned,
} from "./code-studio-gate";
import { Term } from "@/components/ui/Term";

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

type BusyAction = "validate" | "test" | "bind" | "zip" | "probe" | null;
type CodePath = "live" | "option_a";

function reportCodeStudioApiError(err: unknown): string {
  const raw = formatApiError(err);
  reportApiError(new Error(presentCodeStudioError(raw).message), undefined, { toast: true });
  return raw;
}

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

function ResultPanel({
  tone,
  title,
  children,
  testId,
}: {
  tone: "pass" | "blocked" | "error" | "stale";
  title: string;
  children?: React.ReactNode;
  testId?: string;
}) {
  return (
    <div className="cs-result" data-tone={tone} data-testid={testId} role="status">
      <p className="cs-result-title">
        {tone === "pass" ? (
          <Check className="h-4 w-4 shrink-0" aria-hidden />
        ) : (
          <CircleAlert className="h-4 w-4 shrink-0" aria-hidden />
        )}
        <span>{title}</span>
      </p>
      {children ? <div className="cs-result-body">{children}</div> : null}
    </div>
  );
}

function ChecklistItem({
  ok,
  optional,
  failed,
  children,
}: {
  ok: boolean;
  optional?: boolean;
  failed?: boolean;
  children: React.ReactNode;
}) {
  const state = ok ? "true" : failed ? "failed" : optional ? "optional" : "false";
  return (
    <li className="cs-check" data-ok={state}>
      <span className="cs-check-mark" aria-hidden="true">
        {ok ? <Check className="h-3 w-3" strokeWidth={2.5} /> : failed ? "!" : null}
      </span>
      <span>{children}</span>
      <span className="sr-only">
        {ok ? "(done)" : failed ? "(failed)" : optional ? "(optional)" : "(not yet)"}
      </span>
    </li>
  );
}

export function CodeStudioScreen({ connectionId }: { connectionId: string }) {
  const shell = useShellOptional();
  const pathGroupId = useId();

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
  const [path, setPath] = useState<CodePath>("live");
  const [pathTouched, setPathTouched] = useState(false);
  const [validated, setValidated] = useState<Pinned<CodeStudioValidateResult> | null>(null);
  const [tested, setTested] = useState<Pinned<CodeStudioTestRunResult> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<BusyAction>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmRisks, setConfirmRisks] = useState<string[]>([]);
  const [contextHydrated, setContextHydrated] = useState(false);
  const [modKey, setModKey] = useState("Ctrl");

  useSyncShellContext({ model, draftSummary: `Code Studio: ${name}` });

  useEffect(() => {
    if (typeof navigator !== "undefined" && /mac|iphone|ipad/i.test(navigator.platform || navigator.userAgent)) {
      setModKey("⌘");
    }
  }, []);

  const probeOk = Boolean(gate?.probe && (gate.probe as { supported?: boolean }).supported);
  const authoring = useMemo(() => authoringGate(code, validated), [code, validated]);
  const validation = authoring.validation;
  const diagnostics = useMemo(() => diagnosticsFor(code, validation), [code, validation]);
  const currentTest = tested && tested.code === code ? tested.result : null;
  const testGate = testRunGate(authoring, probeOk);
  const bindGate = liveBindGate(authoring, probeOk, tested, code);
  const zipGate = optionAGate(authoring);
  const steps = railSteps({ gate: authoring, path, test: tested, code, probeOk });
  const isBusy = busy !== null;

  const gateSummary = (() => {
    const strip = (text: string | null) => (text ?? "Validate this code first.").replace(/\.$/, "");
    if (path === "live") {
      if (bindGate.ready) {
        return "Authoring gate passed on this code. Bind live is unlocked; the confirm phrase comes next.";
      }
      if (authoring.status === "passed") {
        return `Authoring gate passed on this code. ${bindGate.reason ?? ""}`.trim();
      }
      return `Authoring gate: ${strip(bindGate.reason)}.`;
    }
    if (authoring.status === "passed") {
      return "Authoring gate passed on this code. The zip is unlocked. Nothing installs from here.";
    }
    if (authoring.status === "blocked") {
      return "Blocked server-action rules found. The zip is still available; live bind is not.";
    }
    return `Authoring gate: ${strip(zipGate.reason)}.`;
  })();

  const refresh = useCallback(async () => {
    setContextHydrated(false);
    setError(null);
    try {
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
    } catch (err) {
      setError(reportCodeStudioApiError(err));
    } finally {
      setContextHydrated(true);
    }
  }, [connectionId]);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  // A refused probe means live bind can never run here: open on the Option A path.
  useEffect(() => {
    if (gate && !probeOk && !pathTouched) setPath("option_a");
  }, [gate, probeOk, pathTouched]);

  function choosePath(next: CodePath) {
    setPathTouched(true);
    setPath(next);
  }

  function onCodeChange(next: string) {
    setCode(next);
    setNotice(null);
  }

  async function runValidate() {
    if (isBusy || code.trim() === "") return;
    const judged = code;
    setBusy("validate");
    setError(null);
    setNotice(null);
    try {
      const res = await api.validateCodeStudio(connectionId, judged);
      setValidated({ code: judged, result: res });
    } catch (err) {
      setError(reportCodeStudioApiError(err));
    } finally {
      setBusy(null);
    }
  }

  async function runTest() {
    if (!testGate.ready) return;
    const judged = code;
    setBusy("test");
    setError(null);
    setTested(null);
    try {
      const rid = recordId.trim() ? Number(recordId) : null;
      const res = await api.testRunCodeStudio(connectionId, {
        model,
        record_id: rid,
        code: judged,
      });
      setTested({ code: judged, result: res });
      setValidated({ code: judged, result: res.validation });
    } catch (err) {
      setError(reportCodeStudioApiError(err));
    } finally {
      setBusy(null);
    }
  }

  function openBindConfirm() {
    if (!bindGate.ready) return;
    setConfirmRisks([
      "Python runs with the Odoo credentials on this connection",
      "A snapshot is saved before the server action is written",
    ]);
    setConfirmOpen(true);
  }

  async function confirmBind(phrase: string) {
    if (!bindGate.ready) {
      setConfirmOpen(false);
      return;
    }
    setBusy("bind");
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
        confirm_phrase: phrase,
      });
      const message = `Bound ${res.bind_kind}. Snapshot ${res.snapshot_id ?? "missing"}.`;
      setNotice(message);
      toast.success("Server action bound", {
        description: `Snapshot ${res.snapshot_id ?? "missing"}. The action is live on this database.`,
      });
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmRisks(err.risks);
        setConfirmOpen(true);
      } else {
        setError(reportCodeStudioApiError(err));
      }
    } finally {
      setBusy(null);
    }
  }

  async function downloadOptionA() {
    if (!zipGate.ready) return;
    setBusy("zip");
    setError(null);
    setNotice(null);
    try {
      const res = await api.exportCodeStudioOptionA(connectionId, { name, model, code });
      downloadBase64Zip(res.filename, res.content_base64);
      setNotice(res.note);
      toast.success("Module zip downloaded", { description: res.note });
    } catch (err) {
      setError(reportCodeStudioApiError(err));
    } finally {
      setBusy(null);
    }
  }

  async function reprobe() {
    setBusy("probe");
    setError(null);
    try {
      await api.probeCodeStudio(connectionId);
      await refresh();
      setNotice("Capability probe refreshed.");
    } catch (err) {
      setError(reportCodeStudioApiError(err));
    } finally {
      setBusy(null);
    }
  }

  const expertDraftQuestion = useMemo(
    () =>
      `Draft a safe_eval server action for model ${model}. Context: records, record, model, env, log, UserError. Return Python only. No imports.`,
    [model],
  );
  const presentedError = error ? presentCodeStudioError(error) : null;
  const lineCount = code.length > 0 ? code.split("\n").length : 0;

  const validationPanel = (() => {
    if (authoring.status === "stale") {
      return (
        <ResultPanel tone="stale" title="This code changed. Validate again." testId="code-studio-stale">
          The last pass was for an earlier version. Test run, bind, and the zip stay locked until
          this version passes.
        </ResultPanel>
      );
    }
    if (!validation) return null;
    if (!validation.ok || !validation.syntax_ok) {
      return (
        <ResultPanel tone="error" title="Validation failed" testId="code-studio-validation">
          <p>{validation.error}</p>
          <p className="cs-next">
            Fix {validation.line ? `line ${validation.line}` : "the marked line"}, then validate again.
          </p>
        </ResultPanel>
      );
    }
    if (authoring.status === "blocked") {
      return (
        <ResultPanel tone="blocked" title="Blocked on the server-action path" testId="code-studio-validation">
          <ul className="cs-rule-list">
            {validation.warnings.map((w) => (
              <li key={`${w.code}-${w.line ?? ""}`}>
                <code className="cs-code">{w.code}</code>
                {w.line ? <span className="cs-rule-line">line {w.line}</span> : null}
                <span>{w.message}</span>
              </li>
            ))}
          </ul>
          <p className="cs-next">
            Remove these lines, then validate again. Live bind stays off. The custom-code zip can carry
            them, but a sandbox must prove the module.
          </p>
        </ResultPanel>
      );
    }
    return (
      <ResultPanel tone="pass" title="Validated. The authoring gate passed." testId="code-studio-validation">
        No syntax errors and no blocked rules in this code.{" "}
        {path === "live"
          ? probeOk
            ? "Next: test it on one record, or bind it."
            : "Bind stays off until the instance probe clears."
          : "Next: download the module zip."}
      </ResultPanel>
    );
  })();

  return (
    <OperateStudioChrome
      testIdPrefix="code-studio"
      pageTestId="code-studio-page"
      kicker={connection?.name ?? connectionId}
      title={PAGE_TITLE}
      subtitle={PAGE_DESCRIPTION}
      badge={codeStudioSessionBadge(authoring.status)}
      honesty={codeStudioHonestyGuide()}
      sanitize={sanitizeCodeStudioCopy}
      shellClassName="code-studio-operate"
      className="p-4 sm:p-6"
    >
      <div data-gate={authoring.status} className="contents">
      {connection ? <FirstWriteInterstitial connection={connection} /> : null}

      <CodeStudioHonesty />

      {presentedError ? (
        <ErrorNotice
          message={presentedError.message}
          details={presentedError.details}
          onRetry={() => refresh().catch(() => undefined)}
        />
      ) : null}
      {notice ? (
        <ResultMotion>
          <div className="cs-notice" role="status" data-testid="code-studio-success">
            <Check className="h-4 w-4 shrink-0" aria-hidden />
            <span>{notice}</span>
          </div>
        </ResultMotion>
      ) : null}

      {!contextHydrated && !gate ? (
        <div className="cs-loading" data-testid="code-studio-loading" aria-busy="true" aria-live="polite">
          <Skeleton className="h-14 w-full" />
          <div className="cs-loading-grid">
            <Skeleton className="h-72 w-full" />
            <Skeleton className="h-72 w-full" />
          </div>
          <p className="text-sm text-muted">Loading Code Studio for this connection.</p>
        </div>
      ) : null}

      {gate ? (
        <>
          {!probeOk ? (
            <div className="cs-gating">
              <GatingCallout gating={gate.gating} selectedChoice={null} onSelectChoice={() => undefined} />
              <Button variant="secondary" size="sm" onClick={reprobe} disabled={isBusy} loading={busy === "probe"}>
                Re-probe instance
              </Button>
            </div>
          ) : null}

          <fieldset className="cs-path">
            <legend className="cs-path-legend">Which path</legend>
            <div className="cs-path-options">
              {(
                [
                  {
                    value: "live",
                    title: "Live server action",
                    desc: probeOk
                      ? "Binds state=code on this database after Validate and the confirm phrase."
                      : "Not available: the instance probe has not cleared it.",
                  },
                  {
                    value: "option_a",
                    title: "Custom-code module",
                    desc: "Downloads a zip. Nothing is installed or published here.",
                  },
                ] as const
              ).map((opt) => {
                const titleId = `${pathGroupId}-${opt.value}-title`;
                const descId = `${pathGroupId}-${opt.value}-desc`;
                return (
                  <label key={opt.value} className="cs-path-option" data-checked={path === opt.value ? "true" : undefined}>
                    <input
                      type="radio"
                      name="code-studio-path"
                      value={opt.value}
                      checked={path === opt.value}
                      onChange={() => choosePath(opt.value)}
                      aria-labelledby={titleId}
                      aria-describedby={descId}
                    />
                    <span className="cs-path-text">
                      <span id={titleId} className="cs-path-title">
                        {opt.title}
                      </span>
                      <span id={descId} className="cs-path-desc">
                        {opt.desc}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          <CodeStudioGateRail steps={steps} summary={gateSummary} />

          <div className="cs-grid">
            <section className="cs-editor" aria-label="Editor">
              <div className="cs-editor-bar">
                <span className="cs-file">
                  <span className="cs-file-name">server_action.py</span>
                  <span className="cs-file-meta">
                    {model} · {lineCount} {lineCount === 1 ? "line" : "lines"}
                  </span>
                </span>
                <span className="cs-gate-pill" data-status={authoring.status} data-testid="code-studio-gate-pill">
                  {authoring.label}
                </span>
              </div>
              <div className="cs-editor-tools">
                <h2 className="cs-section-title">Editor</h2>
                <div className="cs-editor-tool-row">
                  <ExplainThisButton
                    question={`Explain this Odoo server action code in safe_eval context:\n\n${code}`}
                    label="Explain this code"
                  />
                  {shell ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      type="button"
                      onClick={() => shell.openExpert({ question: expertDraftQuestion })}
                    >
                      Draft code for me
                    </Button>
                  ) : null}
                  <Select
                    value=""
                    onChange={(e) => {
                      const sn = snippets.find((s) => s.id === e.target.value);
                      if (sn) onCodeChange(sn.code);
                    }}
                    aria-label="Insert snippet"
                    placeholder="Insert snippet…"
                    options={snippets.map((s) => ({ value: s.id, label: s.label }))}
                  />
                </div>
              </div>
              <div className="cs-editor-body">
                <PythonLineEditor
                  value={code}
                  onChange={onCodeChange}
                  label="Python"
                  showHeader={false}
                  diagnostics={diagnostics}
                  testId="code-studio-editor"
                  onSubmit={runValidate}
                />
              </div>
              <div className="cs-actionbar">
                <Button
                  variant="primary"
                  onClick={runValidate}
                  disabled={isBusy || code.trim() === ""}
                  loading={busy === "validate"}
                  data-testid="code-studio-validate"
                  className="cs-press"
                >
                  Validate code
                </Button>
                <Button
                  variant="secondary"
                  onClick={runTest}
                  disabled={isBusy || !testGate.ready}
                  loading={busy === "test"}
                  aria-describedby={testGate.reason ? "code-studio-test-block" : undefined}
                  className="cs-press"
                >
                  Test run on record
                </Button>
                <span className="cs-hint" aria-hidden="true">
                  <Kbd>{modKey}</Kbd>
                  <Kbd>Enter</Kbd>
                  <span>to validate</span>
                </span>
              </div>
              {testGate.reason && path === "live" ? (
                <p id="code-studio-test-block" className="cs-block-reason">
                  <Lock className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  Test run: {testGate.reason}
                </p>
              ) : null}
              <div className="cs-results" aria-live="polite">
                {validationPanel ? (
                  <ResultMotion>{validationPanel}</ResultMotion>
                ) : authoring.status === "unchecked" ? (
                  <p className="cs-idle" data-testid="code-studio-idle">
                    Validate checks syntax and the blocked rules: import, sudo, and unlink. Test run,
                    bind, and the zip stay locked until it passes.
                  </p>
                ) : null}
                {currentTest ? (
                  <ResultMotion>
                    <div data-testid="code-studio-test-result" className="cs-test">
                      <ResultPanel
                        tone={currentTest.ok ? "pass" : "error"}
                        title={currentTest.ok ? "Test passed" : "Test failed"}
                      >
                        <p>{currentTest.exception ?? "Completed without an exception."}</p>
                        {currentTest.snapshot_id ? (
                          <p className="cs-snapshot">Snapshot {currentTest.snapshot_id}.</p>
                        ) : null}
                        {!currentTest.ok ? (
                          <p className="cs-next">Fix the code, validate again, then run the test again.</p>
                        ) : null}
                      </ResultPanel>
                      {currentTest.field_diff.length ? (
                        <CodeBlock language="json" code={JSON.stringify(currentTest.field_diff, null, 2)} />
                      ) : (
                        <p className="cs-muted-line">No scalar field changes detected.</p>
                      )}
                    </div>
                  </ResultMotion>
                ) : null}
              </div>
            </section>

            <div className="cs-side">
              {path === "live" ? (
                <section className="cs-panel" aria-labelledby="code-studio-bind-title" data-testid="code-studio-bind">
                  <h2 id="code-studio-bind-title" className="cs-section-title">
                    Bind live action
                  </h2>
                  <p className="cs-panel-lede">
                    Opens the confirm phrase. The snapshot is saved before the <Term tech="ir.actions.server">server action</Term> is written.
                  </p>
                  <ul className="cs-checklist" aria-label="Before bind" data-testid="code-studio-bind-checklist">
                    <ChecklistItem ok={probeOk}>Instance probe cleared</ChecklistItem>
                    <ChecklistItem ok={authoring.status === "passed"}>Validate passed on this code</ChecklistItem>
                    <ChecklistItem
                      ok={Boolean(currentTest?.ok)}
                      failed={Boolean(currentTest && !currentTest.ok)}
                      optional
                    >
                      {currentTest && !currentTest.ok ? "Last test run failed" : "Test run on one record"}
                    </ChecklistItem>
                  </ul>
                  <div className="cs-fields">
                    <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} />
                    <Select
                      label="Model"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      options={models.map((m) => ({ value: m.model, label: m.model }))}
                    />
                    <Input
                      label="Test record ID"
                      value={recordId}
                      inputMode="numeric"
                      onChange={(e) => setRecordId(e.target.value)}
                      placeholder="Optional, for the test run"
                    />
                    <Select
                      label="Bind as"
                      value={bindKind}
                      onChange={(e) => setBindKind(e.target.value as (typeof BIND_KINDS)[number]["value"])}
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
                  </div>
                  {bindGate.reason ? (
                    <p id="code-studio-bind-block" className="cs-block-reason" data-testid="code-studio-bind-block">
                      <Lock className="h-3.5 w-3.5 shrink-0" aria-hidden />
                      <span>
                        {bindGate.reason}
                        {currentTest && !currentTest.ok && currentTest.snapshot_id
                          ? ` Snapshot ${currentTest.snapshot_id}.`
                          : ""}
                      </span>
                    </p>
                  ) : null}
                  <Button
                    type="button"
                    variant="secondary"
                    className="cs-press w-full"
                    disabled={isBusy || !bindGate.ready}
                    loading={busy === "bind"}
                    aria-describedby={bindGate.reason ? "code-studio-bind-block" : undefined}
                    onClick={openBindConfirm}
                  >
                    Bind live action
                  </Button>
                </section>
              ) : (
                <section className="cs-panel" aria-labelledby="code-studio-zip-title" data-testid="code-studio-option-a">
                  <h2 id="code-studio-zip-title" className="cs-section-title">
                    Download custom-code zip
                  </h2>
                  <p className="cs-panel-lede cs-panel-lede-strong">
                    The zip is the module. Nothing is installed on this connection, and nothing is published.
                  </p>
                  <ul className="cs-checklist" aria-label="Before download">
                    <ChecklistItem ok={zipGate.ready}>Validate passed on this code</ChecklistItem>
                    <ChecklistItem ok={false} optional>
                      Sandbox proof, after download
                    </ChecklistItem>
                    <ChecklistItem ok={false} optional>
                      Promote by a person, outside this screen
                    </ChecklistItem>
                  </ul>
                  <div className="cs-fields">
                    <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} />
                    <Select
                      label="Model"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      options={models.map((m) => ({ value: m.model, label: m.model }))}
                    />
                  </div>
                  {zipGate.reason ? (
                    <p id="code-studio-zip-block" className="cs-block-reason" data-testid="code-studio-zip-block">
                      <Lock className="h-3.5 w-3.5 shrink-0" aria-hidden />
                      <span>{zipGate.reason}</span>
                    </p>
                  ) : null}
                  <Button
                    type="button"
                    variant="secondary"
                    className="cs-press w-full"
                    onClick={downloadOptionA}
                    disabled={isBusy || !zipGate.ready}
                    loading={busy === "zip"}
                    aria-describedby={zipGate.reason ? "code-studio-zip-block" : undefined}
                  >
                    Download module zip
                  </Button>
                </section>
              )}

              <section className="cs-panel" aria-labelledby="code-studio-context-title">
                <h2 id="code-studio-context-title" className="cs-section-title">
                  safe_eval context
                </h2>
                <p className="cs-panel-lede">
                  Odoo {connection?.server_version ?? "version unknown"}. Documented server-action symbols.
                </p>
                {!contextHydrated ? (
                  <div className="space-y-2" data-testid="code-studio-symbols-loading">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-5/6" />
                    <Skeleton className="h-4 w-4/6" />
                  </div>
                ) : symbols.length === 0 ? (
                  <EmptyState
                    title="No safe_eval symbols"
                    description="Re-probe Code Studio if this instance should expose server-action context."
                    action={
                      <Button type="button" variant="secondary" size="sm" onClick={reprobe} disabled={isBusy}>
                        Re-probe instance
                      </Button>
                    }
                  />
                ) : (
                  <dl className="cs-symbols" data-testid="code-studio-symbols-list">
                    {symbols.map((s) => (
                      <div key={s.name} className="cs-symbol">
                        <dt>
                          <code className="cs-code">{s.name}</code>
                        </dt>
                        <dd>{s.description}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </section>
            </div>
          </div>
        </>
      ) : null}

      <ConfirmDialogV2
        open={confirmOpen}
        title="Bind live Python"
        warning="You are binding live Python (state=code) on this database. The snapshot is saved before the write."
        risks={confirmRisks.length ? confirmRisks : ["Runs with Odoo credentials on this connection"]}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => confirmBind(phrase)}
        busy={busy === "bind"}
        riskLevel="danger"
        snapshotNote="A snapshot is created before the server action is written."
      />
      </div>
    </OperateStudioChrome>
  );
}