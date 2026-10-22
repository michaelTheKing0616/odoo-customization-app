"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { OperateStudioBar } from "@/components/operate-studio/OperateStudioBar";
import { ScriptRunnerErrorNotice } from "@/components/script-runner/ScriptRunnerErrorNotice";
import { ScriptRunnerStageRail } from "@/components/script-runner/ScriptRunnerStageRail";
import { ScriptRunnerStateGuide } from "@/components/script-runner/ScriptRunnerStateGuide";
import {
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
  succeededScriptRunnerGuide,
  type ScriptRunnerStepIndex,
} from "@/lib/scriptRunnerScreen";
import "@/components/script-runner/script-runner-operate.css";

const STATES = [
  "empty",
  "idle",
  "confirm",
  "running",
  "succeeded",
  "failed",
  "observer",
  "error",
] as const;
type HarnessState = (typeof STATES)[number];

function stepFor(state: HarnessState): ScriptRunnerStepIndex {
  if (state === "confirm") return 2;
  if (state === "running" || state === "succeeded" || state === "failed") return 3;
  return 1;
}

function ScriptRunnerHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "idle";
  const state = (STATES.includes(raw as HarnessState) ? raw : "idle") as HarnessState;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const sampleScript =
    "log('Hello from Script Runner')\npartners = env['res.partner'].search([], limit=5)\n";
  const step = stepFor(state);
  const showHonesty = state !== "succeeded" && state !== "failed";

  return (
    <div
      className="script-runner-operate op-studio-shell p-4 sm:p-6"
      data-testid="script-runner-page"
      data-harness-state={state}
      aria-busy={state === "running"}
    >
      <header className="op-studio" data-testid="script-runner-studio-chrome">
        <div className="op-titlebar">
          <div className="op-title-block">
            <p className="op-kicker">E2E mock connection</p>
            <h1 className="op-title">{PAGE_TITLE}</h1>
            <p className="op-subtitle">{PAGE_DESCRIPTION}</p>
          </div>
        </div>
        <OperateStudioBar
          testIdPrefix="script-runner"
          badge={scriptRunnerSessionBadge(step)}
          honesty={showHonesty ? scriptRunnerHonestyGuide() : null}
          hint={
            state === "succeeded"
              ? "Last run succeeded. Snapshot restore is only partly recoverable."
              : "Last run failed. Fix the error, then Run script again."
          }
          sanitize={sanitizeScriptRunnerCopy}
        />
        <ScriptRunnerStageRail step={step} />
      </header>

      <div className="op-desk">
        <div className="op-paper">
          <div className="sr-limits" data-testid="script-runner-limits">
            <h2 className="sr-limits-title">What this run can do</h2>
            <p className="sr-limits-body">{SANDBOX_LIMITS}</p>
          </div>

          {state === "error" ? (
            <ScriptRunnerErrorNotice
              message="Connection timed out while loading templates"
              context="load"
            />
          ) : null}

          {state === "observer" ? (
            <ScriptRunnerStateGuide
              tone="warning"
              testId="script-runner-observer"
              guide={observerScriptRunnerGuide()}
            />
          ) : null}

          {state === "empty" ? (
            <ScriptRunnerStateGuide
              density="brief"
              testId="script-runner-empty-guide"
              guide={emptyScriptRunnerGuide()}
              actions={
                <Button type="button" variant="secondary" size="sm">
                  {PRIMARY_CTA}
                </Button>
              }
            />
          ) : null}

          {state === "idle" || state === "confirm" ? (
            <ScriptRunnerStateGuide
              density="brief"
              testId="script-runner-idle-guide"
              guide={idleScriptRunnerGuide()}
            />
          ) : null}

          {state === "running" ? (
            <div
              className="sr-progress"
              aria-busy="true"
              data-testid="script-runner-progress"
              aria-live="polite"
            >
              Running the script. Output appears when the run finishes.
            </div>
          ) : null}

          {state === "succeeded" ? (
            <ScriptRunnerStateGuide
              tone="success"
              testId="script-runner-success"
              guide={succeededScriptRunnerGuide({ writeCount: 3, snapshotId: "snap_sr_9a2c" })}
            />
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
                <Button
                  variant="primary"
                  disabled={state === "running" || state === "observer"}
                  data-testid="script-runner-run-btn"
                >
                  {state === "running" ? "Running…" : PRIMARY_CTA}
                </Button>
                {state === "running" ? (
                  <Button variant="secondary" data-testid="script-runner-abort">
                    Abort
                  </Button>
                ) : null}
              </div>
              <div
                className="rounded-lg border border-border-subtle bg-surface-muted p-3 font-mono text-xs leading-relaxed text-ink"
                data-testid="script-runner-editor"
                aria-label="Script"
              >
                {sampleScript.split("\n").map((line, i) => (
                  <div key={i} className="flex gap-3">
                    <span className="w-6 shrink-0 text-right text-muted tabular-nums">{i + 1}</span>
                    <span className="token">{line || " "}</span>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap items-end gap-2">
                <Input id="script-runner-save-name" label="Save as" defaultValue="" placeholder="My batch script" />
                <Button variant="secondary" size="sm">
                  Save to library
                </Button>
              </div>
              <div className="sr-console">
                <h3 className="sr-console-title">Console</h3>
                <pre className="sr-console-pre" data-testid="script-runner-console" aria-live="polite">
                  {state === "running"
                    ? "Running the script. Output appears when the run finishes."
                    : state === "succeeded"
                      ? "Hello from Script Runner\n\nWrite counts: {\n  \"res.partner.write\": 3\n}"
                      : state === "failed"
                        ? "Traceback (most recent call last):\nAccessError: You are not allowed to modify 'res.users'"
                        : "Output appears here after a run."}
                </pre>
              </div>
            </section>

            <div className="space-y-4">
              <section className="sr-panel space-y-3" data-testid="script-runner-last-run">
                <h2 className="sr-panel-title">Last run</h2>
                {state === "empty" || state === "idle" || state === "confirm" || state === "observer" || state === "error" ? (
                  <p className="text-sm text-muted">{emptyScriptRunnerGuide().why}</p>
                ) : null}
                {state === "running" ? <p className="text-sm text-muted">Run in progress.</p> : null}
                {state === "succeeded" ? (
                  <div className="space-y-2 text-sm">
                    <p className="sr-result-label" data-testid="script-runner-result-label">
                      {resultHonestyLabel(true)}
                    </p>
                    <p>
                      <span className="font-medium text-ink">Succeeded</span>
                      <span className="text-muted"> · 3 writes</span>
                    </p>
                    <p className="sr-mono">Hash a1b2c3d4e5f6</p>
                    <div className="space-y-2" data-testid="script-runner-restore">
                      <p className="text-sm text-ink">
                        Snapshot snap_sr_9a2c was taken before this write. {RESTORE_NOTE}
                      </p>
                      <Link
                        href="/connections/conn-1/journal"
                        className="inline-flex min-h-10 items-center text-sm font-medium text-accent underline-offset-2 hover:underline"
                      >
                        Open the journal
                      </Link>
                    </div>
                  </div>
                ) : null}
                {state === "failed" ? (
                  <div className="space-y-2 text-sm">
                    <p className="sr-result-label" data-testid="script-runner-result-label">
                      {resultHonestyLabel(false)}
                    </p>
                    <ScriptRunnerStateGuide
                      tone="danger"
                      live
                      testId="script-runner-failure"
                      guide={failedScriptRunnerGuide(
                        "AccessError: You are not allowed to modify 'res.users'",
                      )}
                    />
                  </div>
                ) : null}
              </section>

              <section className="sr-panel space-y-3" data-testid="script-runner-library-panel">
                <h2 className="sr-panel-title">Saved scripts</h2>
                {state === "empty" ? (
                  <p className="text-sm text-muted">No saved scripts yet.</p>
                ) : (
                  <ul className="space-y-2 text-xs" data-testid="script-runner-library">
                    <li className="sr-history-item">
                      <button type="button" className="sr-library-btn">
                        Partner sample
                      </button>
                      <p className="text-muted">Search five partners and log names.</p>
                    </li>
                  </ul>
                )}
              </section>

              <section className="sr-panel space-y-3" data-testid="script-runner-history-panel">
                <h2 className="sr-panel-title">Run history</h2>
                {state === "succeeded" || state === "failed" ? (
                  <ul className="space-y-2 text-xs">
                    <li className="sr-history-item">
                      <span className="font-medium text-ink">
                        {state === "succeeded" ? "Succeeded" : "Failed"}
                      </span>
                      <span className="text-muted"> · run-harness</span>
                      <p className="text-muted">{state === "succeeded" ? "3" : "0"} writes</p>
                    </li>
                  </ul>
                ) : (
                  <p className="text-sm text-muted">No runs logged yet.</p>
                )}
              </section>
            </div>
          </div>
        </div>
      </div>

      {state === "confirm" ? (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center"
          data-testid="confirm-dialog-v2"
          role="dialog"
          aria-modal="true"
          aria-labelledby="sr-confirm-title"
        >
          <div className="w-full max-w-md rounded-xl border border-danger/40 bg-surface-raised p-5 shadow-lg">
            <div className="-mx-5 -mt-5 border-b border-danger/30 bg-danger-subtle px-5 py-4">
              <h2 id="sr-confirm-title" className="text-base font-semibold text-danger">
                Run script
              </h2>
            </div>
            <p className="mt-4 text-sm text-ink">
              There is no test run. This runs your Python with this connection&apos;s Odoo credentials.
              A write is journaled after you confirm.
            </p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted">
              <li>There is no test run. After you confirm, the script uses real Odoo RPC</li>
              <li>Write counts are reported but side effects are not auto-reversed</li>
            </ul>
            <label className="mt-4 block text-sm font-medium text-ink" htmlFor="sr-confirm-input">
              Type I understand the risks
            </label>
            <input
              id="sr-confirm-input"
              data-testid="confirm-dialog-v2-input"
              className="mt-1 w-full rounded-md border border-border-subtle bg-surface px-3 py-2 text-sm"
              defaultValue=""
            />
            <div className="mt-4 flex justify-end gap-2">
              <Button type="button" variant="secondary" data-testid="confirm-dialog-v2-cancel">
                Cancel
              </Button>
              <Button type="button" variant="danger" data-testid="confirm-dialog-v2-confirm" disabled>
                Run script
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function ScriptRunnerHarnessPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness…</main>}>
      <ScriptRunnerHarnessInner />
    </Suspense>
  );
}
