"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { BulkResultTable } from "@/components/ui/BulkResultTable";
import { BulkBlastRadius } from "@/components/bulk/BulkBlastRadius";
import { BulkErrorNotice } from "@/components/bulk/BulkErrorNotice";
import { BulkOpRail } from "@/components/bulk/BulkOpRail";
import { BulkResultCounts } from "@/components/bulk/BulkResultCounts";
import { BulkStateGuide } from "@/components/bulk/BulkStateGuide";
import { OperateStudioBar } from "@/components/operate/OperateStudioBar";
import {
  DISCOVER_CTA,
  DRY_RUN_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  blastRadiusFromState,
  bulkHonestyGuide,
  emptyBulkGuide,
  partialFailureGuide,
  sanitizeBulkCopy,
  type BulkStepIndex,
} from "@/lib/bulkSuiteScreen";
import "@/components/bulk/bulk-operate.css";

const STATES = ["empty", "select", "dry-run", "partial", "progress", "error"] as const;
type HarnessState = (typeof STATES)[number];

function stepFor(state: HarnessState): BulkStepIndex {
  if (state === "empty" || state === "error") return 1;
  if (state === "select") return 2;
  if (state === "dry-run" || state === "progress") return 3;
  return 4;
}

function BulkSuiteHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "empty";
  const state = (STATES.includes(raw as HarnessState) ? raw : "empty") as HarnessState;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const blast =
    state === "dry-run" || state === "partial" || state === "progress"
      ? blastRadiusFromState({
          model: "res.partner",
          selectionMode: "domain",
          idsText: "",
          resultTotal: 412,
          resultFailed: state === "partial" ? 12 : 0,
          dryRunResult: state === "dry-run" || state === "progress",
          modelsTouched: 1,
        })
      : state === "select"
        ? blastRadiusFromState({
            model: "res.partner",
            selectionMode: "ids",
            idsText: "1, 2, 3",
          })
        : blastRadiusFromState({
            model: "res.partner",
            selectionMode: "domain",
            idsText: "",
          });

  const failureGuide =
    state === "partial"
      ? partialFailureGuide({ total: 412, succeeded: 400, failed: 12, model: "res.partner" })
      : null;

  const tableResult =
    state === "dry-run" || state === "partial"
      ? {
          run_id: "harness-run",
          operation: "transition",
          model: "res.partner",
          total: 412,
          succeeded: state === "partial" ? 400 : 412,
          failed: state === "partial" ? 12 : 0,
          per_record: [
            { record_id: 1, display_name: "Acme", ok: true },
            {
              record_id: 2,
              display_name: "Beta",
              ok: state !== "partial",
              error: state === "partial" ? "Access denied" : null,
            },
          ],
          dry_run: state === "dry-run",
          message: state === "dry-run" ? "Test run complete." : "Finished with failures.",
        }
      : null;

  const honesty = bulkHonestyGuide();

  return (
    <div className="bulk-operate" data-testid="bulk-suite-page" data-harness-state={state}>
      <div className="bu-pasteboard">
        <article className="bu-sheet">
          <header className="bu-masthead studio-bar-dark">
            <div className="bu-mast-copy">
              <h1 className="bu-title">{PAGE_TITLE}</h1>
              <p className="bu-lead">{sanitizeBulkCopy(PAGE_DESCRIPTION)}</p>
            </div>
          </header>

          <BulkOpRail step={stepFor(state)} />

          {state === "error" ? (
            <BulkErrorNotice
              message="Connection timed out while discovering transitions"
              context="discover"
            />
          ) : null}

          <OperateStudioBar
            testId="bulk-honesty-guide"
            tone="warning"
            title={honesty.title}
            why={honesty.why}
            next={honesty.next}
          />

          <div className="bu-work" data-testid="bulk-suite-desk">
            {state === "empty" ? (
              <BulkStateGuide testId="bulk-empty-guide" tone="accent" guide={emptyBulkGuide()} />
            ) : null}

            {state === "progress" ? (
              <div
                className="bu-progress"
                aria-busy="true"
                data-testid="bulk-suite-progress"
                role="status"
              >
                Running bulk operation…
              </div>
            ) : null}

            <section className="bu-panel" aria-labelledby="harness-transition-title">
              <h2 id="harness-transition-title" className="bu-panel-title">
                Workflow transition
              </h2>
              <p className="bu-panel-sub">
                Harness twin of /connections/[id]/bulk-suite for vision and axe.
              </p>

              <label className="bu-field">
                Model
                <input id="bulk-suite-model" readOnly className="font-mono" value="res.partner" />
              </label>

              {state !== "empty" && state !== "error" ? (
                <>
                  <label className="bu-field mt-3">
                    Transition method
                    <select defaultValue="action_archive">
                      <option value="action_archive">Archive (action_archive)</option>
                    </select>
                  </label>
                  <p className="bu-safe">Bulk-safe - form button is marked safe for batch.</p>
                  <fieldset className="mt-3 space-y-2 text-sm">
                    <legend className="font-medium text-ink">Record selection</legend>
                    <label className="bu-inline">
                      <input type="radio" readOnly checked={state === "select"} /> Explicit ids
                    </label>
                    <label className="bu-inline ml-4">
                      <input type="radio" readOnly checked={state !== "select"} /> Domain
                    </label>
                  </fieldset>
                </>
              ) : null}

              <BulkBlastRadius blast={blast} />

              <div className="bu-actions">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={state === "empty" || state === "progress"}
                >
                  {DISCOVER_CTA}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={state === "empty" || state === "progress" || state === "error"}
                >
                  {DRY_RUN_CTA}
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  disabled={state === "empty" || state === "progress" || state === "error"}
                  data-testid="bulk-run-primary"
                >
                  {PRIMARY_CTA}
                </Button>
                <p className="bu-primary-reason">
                  Test run first so the blast radius is visible before any write.
                </p>
              </div>
            </section>

            {tableResult ? (
              <section className="bu-panel" data-testid="bulk-results-panel">
                <h2 className="bu-panel-title">Results</h2>
                <BulkResultCounts
                  total={tableResult.total}
                  succeeded={tableResult.succeeded}
                  failed={tableResult.failed}
                  dryRun={Boolean(tableResult.dry_run)}
                />
                {failureGuide ? (
                  <BulkStateGuide
                    className="!mt-3"
                    tone="warning"
                    live
                    testId="bulk-partial-guide"
                    guide={failureGuide}
                  />
                ) : null}
                <div className="mt-4">
                  <BulkResultTable result={tableResult} />
                </div>
              </section>
            ) : null}
          </div>
        </article>
      </div>

      <div className="sr-only" aria-hidden>
        <h2>Mass field edit</h2>
        <h2>Duplicate detection & merge</h2>
        <h2>Bulk activities</h2>
        <h2>Bulk security</h2>
        <h2>Bulk portal access</h2>
        <h2>Bulk send message</h2>
      </div>
    </div>
  );
}

export default function BulkSuiteE2ePage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness…</main>}>
      <BulkSuiteHarnessInner />
    </Suspense>
  );
}
