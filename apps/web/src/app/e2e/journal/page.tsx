"use client";

import { Suspense } from "react";
import { OperateStudioBar } from "@/components/operate-studio/OperateStudioBar";
import { useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/layout-primitives";
import { JournalErrorNotice } from "@/components/journal/JournalErrorNotice";
import { JournalStageRail } from "@/components/journal/JournalStageRail";
import { JournalStateGuide } from "@/components/journal/JournalStateGuide";
import {
  CHAIN_VERIFY_NOTE,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  sanitizeJournalCopy,
  journalSessionBadge,
  PRIMARY_CTA,
  REFRESH_CTA,
  auditReplayGuide,
  emptyJournalGuide,
  healthSweepGuide,
  idleJournalGuide,
  irreversibleGuide,
  journalHonestyGuide,
  partialRollbackGuide,
  reversibilityCopy,
  rollbackSuccessGuide,
  type JournalStepIndex,
} from "@/lib/journalScreen";
import "@/components/journal/journal-operate.css";

const STATES = [
  "empty",
  "idle",
  "partial",
  "irreversible",
  "audit",
  "health",
  "restored",
  "error",
] as const;
type HarnessState = (typeof STATES)[number];

function stepFor(state: HarnessState): JournalStepIndex {
  if (state === "empty" || state === "error") return 1;
  if (state === "restored") return 3;
  if (
    state === "partial" ||
    state === "irreversible" ||
    state === "audit" ||
    state === "health"
  ) {
    return 2;
  }
  return 1;
}

function JournalHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "idle";
  const state = (STATES.includes(raw as HarnessState) ? raw : "idle") as HarnessState;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const showTimeline = state !== "empty" && state !== "error";
  const selectedPartial = state === "partial";
  const selectedIrreversible = state === "irreversible";
  const selectedAudit = state === "audit";
  const selectedHealth = state === "health";

  return (
    <div
      className="journal-operate op-studio-shell p-4 sm:p-6"
      data-testid="journal-page"
      data-harness-state={state}
    >

      <header className="op-studio" data-testid="journal-studio-chrome">
        <div className="op-titlebar">
          <div className="op-title-block">
            <p className="op-kicker">E2E mock connection</p>
            <h1 className="op-title">{PAGE_TITLE}</h1>
            <p className="op-subtitle">{PAGE_DESCRIPTION}</p>
          </div>
        </div>
        <OperateStudioBar
          testIdPrefix="journal"
          badge={journalSessionBadge(stepFor(state))}
          honesty={journalHonestyGuide()}
          sanitize={sanitizeJournalCopy}
        />
        <JournalStageRail step={stepFor(state)} />
      </header>

      <div className="op-desk">
        <div className="op-paper space-y-4">
      

      <div className="jn-tabs" data-testid="journal-tabs">
        <Button type="button" variant="secondary" size="sm" data-active="true">
          Timeline
        </Button>
        <Button type="button" variant="ghost" size="sm">
          Batch flow
        </Button>
      </div>

      <p className="jn-chain-note" data-testid="journal-chain-note">
        {CHAIN_VERIFY_NOTE}
      </p>

      {state === "error" ? (
        <JournalErrorNotice
          className="mt-4"
          message="Connection timed out while loading the journal"
          context="load"
        />
      ) : null}

      {state === "empty" ? (
        <JournalStateGuide
          tone="accent"
          density="brief" testId="journal-empty-guide"
          guide={emptyJournalGuide()}
          actions={
            <Button type="button" variant="secondary" size="sm">
              {REFRESH_CTA}
            </Button>
          }
        />
      ) : null}

      {state === "idle" ? (
        <JournalStateGuide tone="neutral" density="brief" testId="journal-idle-guide" guide={idleJournalGuide()} />
      ) : null}

      {selectedPartial ? (
        <JournalStateGuide
          tone="warning"
          testId="journal-partial-guide"
          guide={partialRollbackGuide()}
        />
      ) : null}

      {selectedIrreversible ? (
        <JournalStateGuide
          tone="danger"
          testId="journal-irreversible-guide"
          guide={irreversibleGuide()}
        />
      ) : null}

      {selectedAudit ? (
        <JournalStateGuide tone="neutral" testId="journal-audit-guide" guide={auditReplayGuide()} />
      ) : null}

      {selectedHealth ? (
        <JournalStateGuide
          tone="warning"
          testId="journal-health-guide"
          guide={healthSweepGuide(2)}
        />
      ) : null}

      {state === "restored" ? (
        <JournalStateGuide
          tone="success"
          live
          testId="journal-rollback-success"
          guide={rollbackSuccessGuide("View form.sale.order", 42)}
        />
      ) : null}

      {showTimeline ? (
        <>
          <div className="jn-filters" data-testid="journal-filters">
            <Button type="button" variant="secondary" size="sm" data-active="true">
              All
            </Button>
            <Button type="button" variant="ghost" size="sm">
              Snapshots
            </Button>
            <Button type="button" variant="ghost" size="sm">
              Audit
            </Button>
            <Button type="button" variant="ghost" size="sm">
              Health
            </Button>
          </div>

          <ul className="jn-timeline" data-testid="journal-timeline">
            <li className="jn-entry" data-kind="snapshot">
              <span className="jn-dot" aria-hidden />
              <div
                className="jn-card"
                data-selected={selectedPartial || state === "idle" || state === "restored" ? "true" : "false"}
              >
                <div className="jn-card-head">
                  <div>
                    <div className="jn-badge-row">
                      <Badge variant="info">Snapshot</Badge>
                      <Badge variant="warning">Partially reversible</Badge>
                    </div>
                    <p className="jn-card-title">Sale order form before field drop</p>
                    <p className="jn-card-meta">ir.ui.view · form.sale.order · 2026-10-05T18:02:11Z</p>
                    <p className="jn-card-note">{reversibilityCopy("partial")}</p>
                  </div>
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    data-testid="journal-rollback-btn"
                    disabled={false}
                  >
                    {PRIMARY_CTA}
                  </Button>
                </div>
              </div>
            </li>

            <li className="jn-entry" data-kind="snapshot">
              <span className="jn-dot" aria-hidden />
              <div
                className="jn-card"
                data-selected={selectedIrreversible ? "true" : "false"}
              >
                <div className="jn-card-head">
                  <div>
                    <div className="jn-badge-row">
                      <Badge variant="info">Snapshot</Badge>
                      <Badge variant="danger">Not reversible</Badge>
                    </div>
                    <p className="jn-card-title">Posted move purge preview</p>
                    <p className="jn-card-meta">account.move · purge-batch · 2026-10-04T09:11:00Z</p>
                    <p className="jn-card-note">{reversibilityCopy("none")}</p>
                  </div>
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    data-testid="journal-rollback-irreversible"
                    disabled
                  >
                    {PRIMARY_CTA}
                  </Button>
                </div>
              </div>
            </li>

            <li className="jn-entry" data-kind="audit">
              <span className="jn-dot" aria-hidden />
              <div className="jn-card" data-selected={selectedAudit ? "true" : "false"}>
                <div className="jn-badge-row">
                  <Badge variant="default">Audit</Badge>
                </div>
                <p className="jn-card-meta mt-2 text-ink">
                  <span className="text-accent">POST</span> /api/connections/c1/snapshots/rollback ·
                  200 · 84ms · 2026-10-05T18:03:01Z
                </p>
              </div>
            </li>

            <li className="jn-entry" data-kind="health">
              <span className="jn-dot" aria-hidden />
              <div className="jn-card" data-selected={selectedHealth ? "true" : "false"}>
                <div className="jn-badge-row">
                  <Badge variant="danger">Health · complete</Badge>
                </div>
                <p className="jn-card-title">
                  Manual sweep<span className="text-danger"> · 2 broken</span>
                </p>
                <p className="jn-card-note">19.0 → 20.0 · Two views missing after upgrade</p>
              </div>
            </li>
          </ul>
        </>
      ) : null}
        </div>
      </div>

    </div>
  );
}

export default function JournalE2EPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness…</main>}>
      <JournalHarnessInner />
    </Suspense>
  );
}
