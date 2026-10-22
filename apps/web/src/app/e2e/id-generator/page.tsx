"use client";

import { Suspense } from "react";
import { OperateStudioBar } from "@/components/operate-studio/OperateStudioBar";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/layout-primitives";
import { IdGeneratorResultCounts } from "@/components/id-generator/IdGeneratorResultCounts";
import { IdGeneratorStageRail } from "@/components/id-generator/IdGeneratorStageRail";
import { IdGeneratorStateGuide } from "@/components/id-generator/IdGeneratorStateGuide";
import {
  APPLY_CTA,
  DRY_RUN_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  sanitizeIdGenCopy,
  idGenSessionBadge,
  PREVIEW_CTA,
  PRIMARY_CTA,
  emptyIdGenGuide,
  formatCodeExample,
  idGenErrorGuide,
  idGenHonestyGuide,
  previewCountsGuide,
  sequenceHonestyGuide,
  type IdGenStepIndex,
} from "@/lib/idGeneratorScreen";
import "@/components/id-generator/id-generator-operate.css";

const STATES = ["empty", "csv-preview", "live-dry-run", "applied", "sequence", "error"] as const;
type HarnessState = (typeof STATES)[number];

function stepFor(state: HarnessState): IdGenStepIndex {
  if (state === "empty" || state === "error") return 1;
  if (state === "csv-preview" || state === "live-dry-run") return 3;
  if (state === "applied" || state === "sequence") return 4;
  return 2;
}

function IdGeneratorHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "empty";
  const state = (STATES.includes(raw as HarnessState) ? raw : "empty") as HarnessState;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const mode = state === "live-dry-run" || state === "applied" || state === "sequence" ? "live" : "csv";
  const step = stepFor(state);
  const honesty = idGenHonestyGuide();
  const sample = formatCodeExample({
    prefix: "INV",
    separator: "-",
    padding: 4,
    initialsLength: 3,
  });

  const previewRows =
    state === "csv-preview" || state === "live-dry-run" || state === "applied" || state === "sequence"
      ? [
          { row: "1", name: "Acme Trading Co", old: "none", neu: "INV-ATC-0001" },
          { row: "2", name: "Beacon Supplies", old: "none", neu: "INV-BS-0002" },
          { row: "3", name: "Cedar Mills", old: "CED-01", neu: "CED-01" },
        ]
      : [];

  const counts =
    state === "csv-preview"
      ? { total: 12, changed: 9, skipped: 3, dryRun: true }
      : state === "live-dry-run"
        ? { total: 12, changed: 9, skipped: 3, succeeded: 0, failed: 0, dryRun: true }
        : state === "applied" || state === "sequence"
          ? { total: 12, changed: 9, skipped: 3, succeeded: 9, failed: 0, dryRun: false }
          : null;

  return (
    <div
      className="idgen-operate op-studio-shell p-4 sm:p-6"
      data-testid="id-generator-page"
      data-harness-state={state}
    >

      <header className="op-studio" data-testid="id-generator-studio-chrome">
        <div className="op-titlebar">
          <div className="op-title-block">
            <p className="op-kicker">E2E mock connection</p>
            <h1 className="op-title">{PAGE_TITLE}</h1>
            <p className="op-subtitle">{PAGE_DESCRIPTION}</p>
          </div>
        </div>
        <OperateStudioBar
          testIdPrefix="id-generator"
          badge={idGenSessionBadge(step)}
          honesty={idGenHonestyGuide()}
          sanitize={sanitizeIdGenCopy}
        />
        <IdGeneratorStageRail step={step} />
      </header>

      <div className="op-desk">
        <div className="op-paper space-y-4">
      <p className="ig-lead">
        {PRIMARY_CTA} is the primary action. Live Apply stays behind test run and the risk phrase.
      </p>
      <div className="ig-sample-code" data-testid="id-generator-sample-code">
        <span data-label="Sample">Sample</span>
        <span>{sample}</span>
      </div>
      

      {state === "error" ? (
        <IdGeneratorStateGuide
          testId="id-generator-error"
          tone="danger"
          live
          guide={idGenErrorGuide("csv_preview", "Connection timed out while reading partners.csv")}
        />
      ) : null}

      <section className="ig-panel" aria-labelledby="harness-source-title">
        <h2 id="harness-source-title" className="ig-panel-title">
          {mode === "csv" ? "Spreadsheet source" : "Live Odoo target"}
        </h2>
        <p className="ig-panel-sub">
          Harness twin of /connections/[id]/id-generator for vision and axe.
        </p>

        {mode === "csv" ? (
          <div className="ig-actions">
            <Button type="button" variant="secondary" size="sm" disabled={state === "empty" || state === "error"}>
              {PREVIEW_CTA}
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={state === "empty" || state === "error"}
              data-testid="id-generator-download"
            >
              {PRIMARY_CTA}
            </Button>
            {state === "empty" || state === "error" ? (
              <span className="ig-primary-reason" data-testid="id-generator-download-reason">
                Preview CSV first so the download includes new codes.
              </span>
            ) : null}
          </div>
        ) : (
          <>
            <div className="ig-grid ig-grid-2">
              <Input label="Model" value="x_blk_wf_item" readOnly className="font-mono text-sm" />
              <Input label="Code field" value="x_ref_code" readOnly className="font-mono text-sm" />
            </div>
            {state === "sequence" ? (
              <IdGeneratorStateGuide
                testId="id-generator-sequence-guide"
                tone="warning"
                guide={sequenceHonestyGuide(true)}
                className="mt-3"
              />
            ) : (
              <IdGeneratorStateGuide
                testId="id-generator-sequence-guide"
                tone="neutral"
                guide={sequenceHonestyGuide(false)}
                className="mt-3"
              />
            )}
            <div className="ig-actions">
              <Button type="button" variant="secondary" size="sm" data-testid="id-generator-dry-run">
                {DRY_RUN_CTA}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={state === "live-dry-run" ? false : state === "applied" || state === "sequence" ? false : true}
                data-testid="id-generator-apply"
              >
                {APPLY_CTA}
              </Button>
              <span className="ig-primary-reason">
                {PRIMARY_CTA} stays on the CSV tab. Apply writes only after test run and the risk phrase.
              </span>
            </div>
          </>
        )}
      </section>

      <section className="ig-panel" aria-labelledby="harness-rules-title">
        <h2 id="harness-rules-title" className="ig-panel-title">
          Code rules
        </h2>
        <div className="ig-grid ig-grid-2">
          <Input label="Prefix" value="INV" readOnly className="font-mono text-sm" />
          <Input label="Separator" value="-" readOnly className="font-mono text-sm" />
          <Input label="Number padding" value="4" readOnly />
          <Input label="Initials length" value="3" readOnly />
        </div>
      </section>

      <section
        className="ig-panel"
        aria-labelledby="harness-preview-title"
        data-testid="id-generator-preview-panel"
      >
        <h2 id="harness-preview-title" className="ig-panel-title">
          Preview
        </h2>
        <p className="ig-panel-sub">
          {state === "applied" || state === "sequence"
            ? "Live Apply result (writes applied for changed rows)."
            : state === "live-dry-run"
              ? "Live test run lists proposed codes with no writes."
              : "CSV preview and download never write Odoo."}
        </p>

        {counts ? (
          <>
            <IdGeneratorStateGuide
              testId="id-generator-counts-guide"
              tone={counts.dryRun ? "accent" : "warning"}
              guide={previewCountsGuide({
                total: counts.total,
                changed: counts.changed,
                skipped: counts.skipped,
                dryRun: counts.dryRun,
                mode: mode === "live" ? "live" : "csv",
              })}
            />
            <IdGeneratorResultCounts
              total={counts.total}
              changed={counts.changed}
              skipped={counts.skipped}
              succeeded={"succeeded" in counts ? counts.succeeded : undefined}
              failed={"failed" in counts ? counts.failed : undefined}
              dryRun={counts.dryRun}
            />
          </>
        ) : null}

        {previewRows.length === 0 && state !== "error" ? (
          <div data-testid="id-generator-preview-empty">
            <IdGeneratorStateGuide
              density="brief" testId="id-generator-empty-guide"
              tone="accent"
              guide={emptyIdGenGuide("csv")}
            />
          </div>
        ) : null}

        {previewRows.length > 0 ? (
          <div className="ig-preview-wrap" data-testid="id-generator-preview-table">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr>
                  <th className="border-b border-border-subtle px-3 py-2 text-muted">Row</th>
                  <th className="border-b border-border-subtle px-3 py-2 text-muted">Name</th>
                  <th className="border-b border-border-subtle px-3 py-2 text-muted">Old</th>
                  <th className="border-b border-border-subtle px-3 py-2 text-muted">New</th>
                </tr>
              </thead>
              <tbody>
                {previewRows.map((r) => (
                  <tr key={r.row}>
                    <td className="border-b border-border-subtle px-3 py-2 font-mono">{r.row}</td>
                    <td className="border-b border-border-subtle px-3 py-2">{r.name}</td>
                    <td className="border-b border-border-subtle px-3 py-2 font-mono">{r.old}</td>
                    <td className="border-b border-border-subtle px-3 py-2 font-mono">{r.neu}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
        </div>
      </div>

    </div>
  );
}

export default function IdGeneratorE2EPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness…</main>}>
      <IdGeneratorHarnessInner />
    </Suspense>
  );
}
