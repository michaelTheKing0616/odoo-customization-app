"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/layout-primitives";
import { CronJobsList } from "@/components/cron/CronJobsList";
import { CronNextRunPreview } from "@/components/cron/CronNextRunPreview";
import { CronStateGuide } from "@/components/cron/CronStateGuide";
import { OperateStudioBar } from "@/components/operate/OperateStudioBar";
import { CronStepRail } from "@/components/cron/CronStepRail";
import type { CronRowOut } from "@/lib/api";
import {
  DRY_RUN_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  RUN_NOW_CTA,
  cronErrorGuide,
  cronHonestyGuide,
  emptyCronGuide,
  formatPreviewNextRun,
  resolveCronTimeZone,
  type CronStepId,
} from "@/lib/cronManagerScreen";
import "@/components/cron/cron-operate.css";

const STATES = ["empty", "list", "select", "dry-run", "error", "compose"] as const;
type HarnessState = (typeof STATES)[number];

const SAMPLE_ROWS: CronRowOut[] = [
  {
    id: 11,
    name: "Mail: Email Queue Manager",
    description: "process outgoing mail queue",
    model_name: "mail.mail",
    interval_number: 1,
    interval_type: "hours",
    active: true,
    nextcall: "2026-10-06 01:00:00",
    lastcall: "2026-10-05 00:00:00",
  },
  {
    id: 12,
    name: "Base: Auto-vacuum",
    description: "clean up old database records",
    model_name: "ir.autovacuum",
    interval_number: 1,
    interval_type: "days",
    active: false,
    nextcall: "2026-10-07 03:00:00",
    lastcall: null,
  },
];

function stepFor(state: HarnessState): CronStepId {
  if (state === "compose") return "save";
  if (state === "dry-run") return "trigger";
  if (state === "select") return "select";
  return "list";
}

function CronManagerHarnessInner() {
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "empty";
  const state = (STATES.includes(raw as HarnessState) ? raw : "empty") as HarnessState;
  const tz = resolveCronTimeZone({ tz: "Africa/Lagos" });
  const selected =
    state === "select" || state === "dry-run" ? new Set<number>([11]) : new Set<number>();
  const rows = state === "empty" || state === "error" ? [] : SAMPLE_ROWS;
  const preview = formatPreviewNextRun(1, "days", tz.timeZone, new Date("2026-10-05T19:00:00Z"));

  return (
    <div
      className="cron-operate p-6"
      data-testid="cron-manager-page"
      data-harness-state={state}
    >
      <PageHeader title={PAGE_TITLE} description={PAGE_DESCRIPTION} />
      <CronStepRail current={stepFor(state)} />

      <OperateStudioBar
        className="mt-3"
        testId="cron-honesty-guide"
        tone="warning"
        title={cronHonestyGuide().title}
        why={cronHonestyGuide().why}
        next={cronHonestyGuide().next}
      />

      <div className="cr-desk" data-testid="cron-manager-desk">

      {state === "error" ? (
        <CronStateGuide
          className="!mt-4"
          testId="cron-error-guide"
          tone="danger"
          live
          guide={cronErrorGuide("load", "Connection timed out while listing crons")}
        />
      ) : null}

      {state === "empty" ? (
        <CronStateGuide className="!mt-4" testId="cron-empty-guide" tone="accent" guide={emptyCronGuide()} />
      ) : null}

      <section className="cr-panel" aria-labelledby="harness-list-title">
        <h2 id="harness-list-title" className="cr-panel-title">
          Scheduled actions
        </h2>
        <p className="cr-panel-sub">Harness twin of /connections/[id]/cron-manager for vision and axe.</p>

        <div className="cr-actions">
          <span className="text-xs text-muted" data-testid="cron-selected-count">
            {selected.size} selected
          </span>
        </div>

        {state !== "empty" && state !== "error" ? (
          <CronJobsList
            rows={rows}
            selected={selected}
            busy={false}
            timeZone={tz.timeZone}
            zoneLabel={tz.label}
            onToggleSelected={() => {}}
            onToggleActive={() => {}}
            onRefresh={() => {}}
          />
        ) : null}

        <div className="cr-actions">
          <Button
            type="button"
            variant="secondary"
            disabled={!selected.size}
            data-testid="cron-dry-run-btn"
          >
            {DRY_RUN_CTA} ({selected.size})
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={!selected.size}
            data-testid="cron-run-now-btn"
          >
            {RUN_NOW_CTA} ({selected.size})
          </Button>
        </div>

        {state === "dry-run" ? (
          <div
            className="cr-result mt-4"
            data-testid="cron-last-run"
            data-dry-run="true"
          >
            <h2 className="cr-panel-title">Test run result (no writes)</h2>
            <p className="text-sm text-ink">Would trigger 1 scheduled action. Nothing was written.</p>
          </div>
        ) : null}
      </section>

      <section className="cr-panel" aria-labelledby="harness-compose-title">
        <h2 id="harness-compose-title" className="cr-panel-title">
          Compose schedule
        </h2>
        <p className="cr-panel-sub">Next-run preview uses the connection timezone when reported.</p>
        <label className="cr-field">
          Name
          <input readOnly value="Nightly maintenance" data-testid="cron-name-input" />
        </label>
        <CronNextRunPreview value={preview} zoneLabel={tz.label} />
        <div className="cr-actions">
          <Button type="button" variant="primary" data-testid="cron-save-btn">
            {PRIMARY_CTA}
          </Button>
        </div>
      </section>
      </div>
    </div>
  );
}

export default function CronManagerHarnessPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness…</main>}>
      <CronManagerHarnessInner />
    </Suspense>
  );
}
