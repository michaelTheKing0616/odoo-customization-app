"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { ImportErrorNotice } from "@/components/import/ImportErrorNotice";
import { ImportResultCounts } from "@/components/import/ImportResultCounts";
import { ImportStageRail } from "@/components/import/ImportStageRail";
import { ImportStateGuide } from "@/components/import/ImportStateGuide";
import { OperateStudioChrome } from "@/components/operate-studio/OperateStudioChrome";
import {
  DRY_RUN_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PARSE_CTA,
  PRIMARY_CTA,
  emptyImportGuide,
  importHonestyGuide,
  importSessionBadge,
  partialFailureGuide,
  sanitizeImportCopy,
  type ImportStepIndex,
} from "@/lib/importScreen";
import "@/components/import/import-operate.css";

const STATES = ["empty", "map", "dry-run", "partial", "progress", "error"] as const;
type HarnessState = (typeof STATES)[number];

function stepFor(state: HarnessState): ImportStepIndex {
  if (state === "empty" || state === "error") return 1;
  if (state === "map" || state === "progress") return 2;
  if (state === "dry-run") return 3;
  return 4;
}

function ImportHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "empty";
  const state = (STATES.includes(raw as HarnessState) ? raw : "empty") as HarnessState;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const dryStrip = {
    created: 12,
    updated: 3,
    skipped: 1,
    failed: 0,
    dryRun: true,
    ok: true,
    message: "Test run complete. No rows written.",
    hasErrorCsv: false,
  };
  const partialStrip = {
    created: 8,
    updated: 2,
    skipped: 0,
    failed: 4,
    dryRun: false,
    ok: false,
    message: "Commit finished with 4 row errors.",
    hasErrorCsv: true,
  };
  const failureGuide = partialFailureGuide(partialStrip);
  const step = stepFor(state);
  const showHonesty = state === "empty" || state === "map" || state === "error" || state === "progress";
  const hint =
    state === "dry-run"
      ? "Test run complete. No rows written. Review the counts, then Commit."
      : state === "partial"
        ? "Commit finished with row errors. Download the error CSV if present."
        : "Ready on this connection.";

  return (
    <OperateStudioChrome
      testIdPrefix="import"
      pageTestId="import-page"
      kicker="E2E harness"
      title={PAGE_TITLE}
      subtitle={PAGE_DESCRIPTION}
      badge={importSessionBadge(step)}
      honesty={showHonesty ? importHonestyGuide() : null}
      hint={hint}
      sanitize={sanitizeImportCopy}
      rail={<ImportStageRail step={step} />}
      shellClassName="import-operate"
      className="p-4 sm:p-6"
    >
      {/* harness-state attr via wrapper — OperateStudioChrome lacks passthrough; stamp on paper child */}
      <div data-harness-state={state} className="contents">
      {state === "error" ? (
        <ImportErrorNotice
          message="Connection timed out while parsing partners.csv"
          context="preview"
        />
      ) : null}

      {state === "empty" ? (
        <ImportStateGuide density="brief" testId="import-empty-guide" guide={emptyImportGuide()} />
      ) : null}

      {state === "progress" ? (
        <div className="im-progress" aria-busy="true" data-testid="import-progress" role="status">
          Committing rows…
        </div>
      ) : null}

      <section className="im-panel" aria-labelledby="harness-upload-title">
        <h2 id="harness-upload-title" className="im-panel-title">
          Upload and map
        </h2>
        <p className="im-panel-sub">Harness twin of /connections/[id]/import for vision and axe.</p>

        {state === "empty" || state === "error" ? (
          <div className="im-toolbar">
            <Button type="button" variant="secondary" size="sm">
              Download template
            </Button>
            <Button type="button" variant="secondary" size="sm" disabled>
              {PARSE_CTA}
            </Button>
          </div>
        ) : null}

        {state === "map" || state === "dry-run" || state === "partial" || state === "progress" ? (
          <>
            <div className="im-map-wrap" data-testid="import-mapping-table">
              <table className="im-map-table">
                <thead>
                  <tr>
                    <th scope="col">CSV column</th>
                    <th scope="col">Odoo field</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  <tr data-gap="false">
                    <td className="font-mono text-xs">name</td>
                    <td>
                      <input readOnly value="name" aria-label="Map name to Odoo field" />
                    </td>
                    <td>
                      <span className="text-xs text-muted">Ready</span>
                    </td>
                  </tr>
                  <tr data-gap="false">
                    <td className="font-mono text-xs">email</td>
                    <td>
                      <input readOnly value="email" aria-label="Map email to Odoo field" />
                    </td>
                    <td>
                      <span className="text-xs text-muted">Ready</span>
                    </td>
                  </tr>
                  <tr data-gap="true">
                    <td className="font-mono text-xs">notes</td>
                    <td>
                      <input readOnly value="" aria-label="Map notes to Odoo field" />
                    </td>
                    <td>
                      <span className="im-gap-chip">Unmapped</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="im-actions">
              <Button type="button" variant="secondary" disabled={state === "progress"}>
                {DRY_RUN_CTA}
              </Button>
              <Button
                type="button"
                variant="primary"
                disabled={state === "progress"}
                data-testid="import-commit-btn"
              >
                {PRIMARY_CTA}
              </Button>
              <p className="im-primary-reason">Test run first to see create, update, skip, and error counts.</p>
            </div>
          </>
        ) : null}

        {state === "dry-run" ? (
          <div className="mt-4" data-testid="import-result-block">
            <p className="text-sm font-medium text-ink">Test run counts</p>
            <ImportResultCounts strip={dryStrip} />
            <p className="mt-2 text-sm text-muted" data-testid="import-result-message">
              {dryStrip.message}
            </p>
          </div>
        ) : null}

        {state === "partial" ? (
          <div className="mt-4" data-testid="import-result-block">
            <p className="text-sm font-medium text-ink">Commit counts</p>
            <ImportResultCounts strip={partialStrip} />
            {failureGuide ? (
              <ImportStateGuide
                className="!mt-3"
                tone="warning"
                live
                testId="import-partial-guide"
                guide={failureGuide}
                actions={
                  <Button type="button" variant="secondary" size="sm" data-testid="import-error-csv-btn">
                    Download error CSV
                  </Button>
                }
              />
            ) : null}
          </div>
        ) : null}
      </section>
      </div>
    </OperateStudioChrome>
  );
}

export default function ImportHarnessPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness…</main>}>
      <ImportHarnessInner />
    </Suspense>
  );
}
