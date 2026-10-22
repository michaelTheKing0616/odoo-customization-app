"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/layout-primitives";
import { ReportsCreateForm } from "@/components/reports/ReportsCreateForm";
import { ReportsListPanel, type ReportListRow } from "@/components/reports/ReportsListPanel";
import { parseQwebRenderError } from "@/components/reports/reportRenderError";
import {
  RENTAL_AGREEMENT_STARTER,
  ReportCanvas,
} from "@/components/reports/ReportCanvas";
import { REPORT_INHERIT_SLOTS } from "@/components/reports/reportInheritSlots";
import styles from "@/components/reports/ReportsPage.module.css";
import { cn } from "@/lib/cn";

/**
 * PDF-06 / UI-S-17 vision harness — Canva pasteboard chrome + inherit + render-error.
 * Gated by NEXT_PUBLIC_E2E. Real ReportCanvas paper (not an AI mock).
 */
type Shot = "desktop" | "empty" | "inherit" | "render-error" | "loading";

const FIXTURE_REPORTS: ReportListRow[] = [
  {
    id: 10,
    name: "Rental agreement",
    model: "x_rent_contract",
    report_name: "custom.report_rent",
    paperformat_name: "A4",
    arch: null,
  },
  {
    id: 11,
    name: "Invoice (stock)",
    model: "account.move",
    report_name: "account.report_invoice",
    paperformat_name: "A4",
    arch: null,
  },
];

const SAMPLE_RENDER_ERROR = "QWebException: Error to render compiling AST\nFile \"custom.report_rent\", line 28, in template\nValueError: Unknown field x_missing";

export default function ReportsStudioHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [shot, setShot] = useState<Shot>("desktop");
  const [selectedId, setSelectedId] = useState<number | null>(10);
  const [form, setForm] = useState({
    name: "Custom document",
    model: "res.partner",
    report_key: "custom.report_partner",
    paperformat_id: "",
  });

  const reports = useMemo(
    () => (shot === "empty" ? [] : FIXTURE_REPORTS),
    [shot],
  );
  const hydrated = shot !== "loading";
  const renderInfo =
    shot === "render-error" ? parseQwebRenderError(SAMPLE_RENDER_ERROR) : null;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <main
      className="min-h-[100dvh] bg-[#f3f3f4] p-4 text-ink md:p-8"
      data-testid="reports-studio-harness"
      data-shot={shot}
    >
      <div className="mb-3 flex flex-wrap items-center gap-1.5 print:hidden">
        <span className="mr-2 text-[11px] font-medium uppercase tracking-[0.06em] text-muted">
          PDF-06
        </span>
        {(
          [
            ["desktop", "Desktop"],
            ["empty", "Empty"],
            ["inherit", "Inherit"],
            ["render-error", "Render error"],
            ["loading", "Loading"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            data-testid={`harness-shot-${id}`}
            className={cn(
              "rounded-md px-2 py-1 text-xs",
              shot === id
                ? "bg-ink text-background"
                : "border border-border-subtle bg-surface text-muted",
            )}
            onClick={() => setShot(id)}
          >
            {label}
          </button>
        ))}
        <button
          type="button"
          data-testid="harness-theme-toggle"
          className="rounded-md border border-border-subtle px-2 py-1 text-xs text-muted"
          onClick={() => document.documentElement.classList.toggle("dark")}
        >
          Theme
        </button>
      </div>

      <div className={`${styles.page} mx-auto max-w-5xl`} data-testid="reports-page">
        <PageHeader
          title="Report layout lite"
          description="Design QWeb PDF printouts on a paper canvas — create from scratch or extend one stock slot."
        />

        <div className="mt-6 space-y-5">
          <ReportsCreateForm
            form={form}
            papers={[{ id: 1, name: "A4" }]}
            onChange={setForm}
            onSubmit={(e) => e.preventDefault()}
          />

          <div className={styles.workbench} data-testid="reports-workbench">
            <ReportsListPanel
              reports={reports}
              selectedId={selectedId}
              hydrated={hydrated}
              onSelect={setSelectedId}
              embedded
            />

            <div className={styles.editorPane} data-testid="reports-editor-panel">
              <div className={styles.editorToolbar}>
                <div className={styles.tabs} role="tablist" aria-label="Report editor">
                  <button type="button" className={cn(styles.tab, styles.tabActive)} role="tab" aria-selected>
                    Visual
                  </button>
                  <button type="button" className={styles.tab} role="tab" aria-selected={false}>
                    QWeb
                  </button>
                </div>
                <Button type="button" variant="primary" size="sm" data-testid="reports-save-arch">
                  Save the printout
                </Button>
                {shot === "inherit" ? (
                  <span className={styles.inheritChip} data-testid="reports-inherit-op-chip">
                    inherit · header slot
                  </span>
                ) : null}
              </div>

              <div className={styles.editorBody}>
                {shot === "inherit" ? (
                  <div
                    className="mb-3 space-y-2 rounded-lg border border-[color-mix(in_srgb,var(--ink,#1a1c21)_10%,transparent)] bg-[color-mix(in_srgb,#fff_70%,transparent)] p-3"
                    data-testid="report-inherit-chrome"
                  >
                    <p className="text-[0.6875rem] font-medium tracking-[-0.01em] text-ink">
                      Extend one slot
                    </p>
                    <p className="text-[11px] text-muted">
                      Base: account.report_invoice
                    </p>
                    <fieldset data-testid="report-inherit-slot-picker" className="grid gap-1">
                      {REPORT_INHERIT_SLOTS.map((entry) => (
                        <label
                          key={entry.slot}
                          className={
                            entry.slot === "header"
                              ? "flex gap-2 rounded-md border border-accent/40 bg-surface-raised px-2 py-1.5 text-xs"
                              : "flex gap-2 rounded-md px-2 py-1.5 text-xs text-muted"
                          }
                        >
                          <input
                            type="radio"
                            name="harness-slot"
                            defaultChecked={entry.slot === "header"}
                            readOnly
                            data-testid={`report-inherit-slot-${entry.slot}`}
                          />
                          {entry.label}
                        </label>
                      ))}
                    </fieldset>
                  </div>
                ) : null}

                {renderInfo ? (
                  <div
                    role="alert"
                    data-testid="report-render-error"
                    className="mb-3 rounded-lg border border-danger/30 bg-danger-subtle p-3 text-sm"
                  >
                    <p className="font-semibold text-danger">{renderInfo.summary}</p>
                    {renderInfo.templateLine != null ? (
                      <p
                        className="mt-1 font-mono text-xs tabular-nums text-muted"
                        data-testid="report-render-error-line"
                      >
                        Template line {renderInfo.templateLine}
                      </p>
                    ) : null}
                    <p className="mt-2 text-xs text-muted whitespace-pre-wrap">
                      {renderInfo.message}
                    </p>
                  </div>
                ) : null}

                {shot === "loading" ? (
                  <div className="space-y-2 p-2" data-testid="report-preview-loading">
                    <Skeleton className="h-3 w-40" />
                    <Skeleton className="h-72 w-full" />
                  </div>
                ) : shot === "empty" ? (
                  <div className={styles.emptyDesk}>
                    <EmptyState
                      title="No custom reports yet"
                      description="Start with New printout — the sheet opens on this desk."
                    />
                  </div>
                ) : (
                  <div data-testid="report-canvas-stage" className="mx-auto max-w-[520px]">
                    <ReportCanvas
                      blocks={RENTAL_AGREEMENT_STARTER}
                      paperLabel="A4"
                      useExternalLayout
                      selectedId="h1"
                      onSelect={() => {}}
                      onMove={() => {}}
                      onAddBlock={() => {}}
                      documentTitle="Rental Agreement"
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
