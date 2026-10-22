"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Card, EmptyState } from "@/components/ui/layout-primitives";
import { DOC_TYPE_OPTIONS, docTypeLabel } from "@/components/ingest/docTypes";
import {
  IngestStepRail,
  type IngestStepId,
} from "@/components/ingest/IngestStepRail";
import { OperateStudioChrome } from "@/components/operate-studio/OperateStudioChrome";
import {
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  emptyIngestGuide,
  ingestHonestyGuide,
  ingestSessionBadge,
  sanitizeIngestCopy,
} from "@/lib/ingestScreen";
import "@/components/ingest/ingest-operate.css";

type HarnessState = "empty" | "planned" | "dry-run" | "override" | "committed";

function IngestE2EInner() {
  const search = useSearchParams();
  const state = (search.get("state") as HarnessState) || "planned";

  const [overrideReason, setOverrideReason] = useState("");
  const [docType, setDocType] = useState("customer_list");

  const gaps =
    state === "planned" || state === "override"
      ? [{ message: "UoM 'crates' not found on instance" }]
      : [];

  const step: IngestStepId = useMemo(() => {
    if (state === "empty") return "upload";
    if (state === "dry-run") return "dry-run";
    if (state === "committed") return "commit";
    if (state === "override") return "classify";
    return "plan";
  }, [state]);

  const canApplyOverrides =
    state === "override" && overrideReason.trim().length >= 3;
  const commitDisabled = gaps.length > 0;
  const showHonesty = state === "empty" || state === "planned" || state === "override";
  const hint =
    state === "dry-run"
      ? "Test run complete. No rows written. Review the log, then Commit."
      : state === "committed"
        ? "Commit applied. Writes are on this live connection."
        : "Ready on this connection.";

  return (
    <OperateStudioChrome
      testIdPrefix="ingest"
      pageTestId="ingest-page"
      kicker="E2E harness"
      title={PAGE_TITLE}
      subtitle={PAGE_DESCRIPTION}
      badge={ingestSessionBadge(step)}
      honesty={showHonesty ? ingestHonestyGuide() : null}
      hint={hint}
      sanitize={sanitizeIngestCopy}
      rail={<IngestStepRail current={step} />}
      shellClassName="ingest-operate"
      className="p-4 sm:p-6"
    >
      <div data-harness-state={state} className="contents">
      {state === "empty" ? (
        <>
          <div className="op-brief" data-testid="ingest-empty-guide">
            <p className="op-brief-title">{emptyIngestGuide().title}</p>
            <dl className="op-brief-rows">
              <dt>Why</dt>
              <dd>{emptyIngestGuide().why}</dd>
              <dt>Next</dt>
              <dd>{emptyIngestGuide().next}</dd>
            </dl>
          </div>
          <Card className="space-y-3 p-4" data-testid="ingest-upload-card">
            <h2 className="ig-panel-title">Upload files</h2>
            <p className="ig-panel-sub">No files selected yet.</p>
            <Button type="button" variant="secondary" data-testid="ingest-analyze-btn" disabled>
              Analyze and plan
            </Button>
          </Card>
        </>
      ) : (
        <Card className="space-y-3 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="ig-panel-title">Classification</h2>
            <span data-testid="ingest-status">
              <Badge>
                {state === "committed"
                  ? "committed"
                  : state === "dry-run"
                    ? "dry_run"
                    : "planned"}
              </Badge>
            </span>
          </div>

          <div className="flex flex-col gap-2 rounded-md border border-border-subtle px-3 py-2 sm:flex-row sm:items-center">
            <span className="font-mono text-sm">partners.csv</span>
            <Badge variant="info">{docTypeLabel(docType)}</Badge>
            <Badge variant="warning" className="tabular-nums">
              42%
            </Badge>
            {state === "override" ? (
              <span data-testid="ingest-needs-confirm">
                <Badge variant="warning">Confirm type</Badge>
              </span>
            ) : null}
            <Select
              aria-label="Document type for partners.csv"
              className="min-w-[11rem]"
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              options={DOC_TYPE_OPTIONS}
              data-testid="ingest-doc-type-f1"
            />
          </div>

          {state === "override" ? (
            <div className="space-y-3 rounded-md border border-warning/30 bg-warning-subtle/40 p-3">
              <Input
                label="Override reason"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="e.g. Filename is a vendor list, not customers"
                data-testid="ingest-override-reason"
              />
              <Button
                type="button"
                variant="secondary"
                disabled={!canApplyOverrides}
                data-testid="ingest-apply-overrides"
              >
                Apply type overrides and rebuild plan
              </Button>
            </div>
          ) : null}

          <ol
            className="list-decimal space-y-2 pl-5 text-sm"
            data-testid="ingest-commit-order"
          >
            <li data-testid="ingest-step-0">res.partner</li>
            <li data-testid="ingest-step-1">product.template</li>
          </ol>

          {gaps.length > 0 ? (
            <Callout
              variant="warning"
              title="Unresolved gaps block commit"
              testId="ingest-gaps"
            >
              <p className="mb-2 text-xs">
                What: missing references or units on this instance. Why: commit
                would create incomplete rows. Next: fix the source file or map
                values, then re-analyze.
              </p>
              <ul className="list-disc pl-4 text-xs">
                {gaps.map((g) => (
                  <li key={g.message}>{g.message}</li>
                ))}
              </ul>
            </Callout>
          ) : null}

          <div className="ig-actions">
            <Button type="button" variant="secondary" data-testid="ingest-dry-run-btn">
              Test run
            </Button>
            <Button
              type="button"
              variant="primary"
              data-testid="ingest-commit-btn"
              disabled={commitDisabled}
            >
              Commit
            </Button>
          </div>

          {gaps.length > 0 ? (
            <p className="text-xs text-danger" data-testid="ingest-gap-block">
              Resolve gaps before commit.
            </p>
          ) : null}

          {state === "dry-run" ? (
            <div
              className="rounded-md border border-border-subtle bg-surface-muted/50 p-3 text-xs"
              data-testid="ingest-commit-log"
              role="status"
            >
              <p className="font-medium text-ink tabular-nums">
                Test run result (no writes): created 12, updated 0, failed 0,
                skipped 1
              </p>
            </div>
          ) : null}

          {state === "committed" ? (
            <div
              className="rounded-md border border-border-subtle bg-surface-muted/50 p-3 text-xs"
              data-testid="ingest-commit-log"
              role="status"
            >
              <p className="font-medium text-ink tabular-nums">
                Commit result (writes applied): created 12, updated 0, failed 0,
                skipped 1
              </p>
            </div>
          ) : null}
        </Card>
      )}
      {/* Keep ingest-honesty test id for legacy e2e that query the folded bar */}
      <span className="sr-only" data-testid="ingest-honesty">
        {showHonesty ? ingestHonestyGuide().title : hint}
      </span>
      </div>
    </OperateStudioChrome>
  );
}

export default function IngestE2EPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading ingest harness…</main>}>
      <IngestE2EInner />
    </Suspense>
  );
}
