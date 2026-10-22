"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/layout-primitives";
import { Textarea } from "@/components/ui/Textarea";
import { PowerOpsErrorNotice } from "@/components/power-ops/PowerOpsErrorNotice";
import { PowerOpsResultCounts } from "@/components/power-ops/PowerOpsResultCounts";
import { PowerOpsStageRail } from "@/components/power-ops/PowerOpsStageRail";
import { PowerOpsStateGuide } from "@/components/power-ops/PowerOpsStateGuide";
import { OperateStudioBar } from "@/components/operate/OperateStudioBar";
import {
  DRY_RUN_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  blockedRecipeGuide,
  emptyPowerOpsGuide,
  idlePowerOpsGuide,
  partialFailureGuide,
  powerOpsHonestyGuide,
  type PowerOpsStepIndex,
} from "@/lib/powerOpsScreen";
import "@/components/power-ops/power-ops-operate.css";

const STATES = ["empty", "idle", "blocked", "dry-run", "danger", "executed", "error"] as const;
type HarnessState = (typeof STATES)[number];

function stepFor(state: HarnessState): PowerOpsStepIndex {
  if (state === "empty" || state === "error") return 1;
  if (state === "idle" || state === "blocked" || state === "danger") return 2;
  if (state === "dry-run") return 3;
  return 4;
}

function PowerOpsHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "idle";
  const state = (STATES.includes(raw as HarnessState) ? raw : "idle") as HarnessState;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const showRecipes = state !== "empty" && state !== "error";
  const dangerActive = state === "danger" || state === "dry-run" || state === "executed";
  const canRun = state === "dry-run" || state === "executed";
  const dryResult = { processed: 12, succeeded: 10, failed: 2, dryRun: true };
  const liveResult = { processed: 12, succeeded: 9, failed: 3, dryRun: false };
  const partial = partialFailureGuide(
    state === "executed"
      ? { ...liveResult, dryRun: false }
      : { ...dryResult, dryRun: true },
  );

  return (
    <div className="power-ops-operate p-6" data-testid="power-ops-page" data-harness-state={state}>
      <PageHeader title={PAGE_TITLE} description={PAGE_DESCRIPTION} />
      <PowerOpsStageRail step={stepFor(state)} />

      <OperateStudioBar
        className="mt-3"
        testId="power-ops-honesty"
        tone="warning"
        title={powerOpsHonestyGuide().title}
        why={powerOpsHonestyGuide().why}
        next={powerOpsHonestyGuide().next}
      />

      <div className="po-desk" data-testid="power-ops-desk">

      {state === "error" ? (
        <PowerOpsErrorNotice
          className="mt-4"
          message="Connection timed out while loading recipes"
          context="load"
        />
      ) : null}

      {state === "empty" ? (
        <PowerOpsStateGuide
          tone="accent"
          testId="power-ops-empty-guide"
          guide={emptyPowerOpsGuide()}
          actions={
            <Button type="button" variant="secondary" size="sm">
              Re-probe connection
            </Button>
          }
        />
      ) : null}

      {showRecipes ? (
        <section className="po-panel" data-testid="power-ops-recipes">
          <h2 className="po-panel-title">Recipes</h2>
          <p className="po-panel-sub">
            Safe recipes first. Danger-zone recipes need test run counts, then the risk phrase.
          </p>
          {state === "idle" || state === "blocked" || state === "danger" ? (
            <PowerOpsStateGuide
              className="!mt-0 mb-3"
              tone="accent"
              testId="power-ops-idle-guide"
              guide={idlePowerOpsGuide()}
            />
          ) : null}
          <div className="po-recipe-grid">
            <button
              type="button"
              className="po-recipe"
              data-active={dangerActive ? "false" : "true"}
              data-danger="false"
              data-testid="power-ops-recipe-mass_archive"
            >
              <div className="po-recipe-head">
                <p className="po-recipe-name">Mass archive</p>
                <Badge variant="info">Odoo ≥16</Badge>
              </div>
              <p className="po-recipe-desc">Set active=false on matching records.</p>
            </button>
          </div>
          <div className="po-danger-band" data-testid="power-ops-danger-zone">
            <p className="po-danger-band-title">Danger zone</p>
            <p className="po-danger-band-body">
              Destructive recipes. Test run first. Run recipe asks for the risk phrase.
            </p>
            <div className="po-recipe-grid">
              <button
                type="button"
                className="po-recipe"
                data-active={dangerActive ? "true" : "false"}
                data-danger="true"
                data-testid="power-ops-recipe-purge_journal_entries"
                disabled={state === "blocked"}
              >
                <div className="po-recipe-head">
                  <p className="po-recipe-name">Purge journal entries</p>
                  <div className="po-badge-row">
                    <Badge variant="danger">Danger zone</Badge>
                    {state === "blocked" ? <Badge variant="warning">needs ≥18</Badge> : null}
                  </div>
                </div>
                <p className="po-recipe-desc">
                  Reset posted account.move rows to draft, then unlink.
                </p>
              </button>
            </div>
          </div>
        </section>
      ) : null}

      {state === "blocked" ? (
        <PowerOpsStateGuide
          tone="warning"
          live
          testId="power-ops-blocked-guide"
          guide={blockedRecipeGuide({
            blockReason: "needs ≥18",
            minMajor: 18,
            major: 16,
          })}
        />
      ) : null}

      {showRecipes && state !== "blocked" ? (
        <section className="po-panel" data-testid="power-ops-run-panel">
          <h2 className="po-panel-title">
            Run · {dangerActive ? "Purge journal entries" : "Mass archive"}
          </h2>
          <p className="po-panel-sub">
            {dangerActive
              ? "Destructive recipe. Confirm only after test run counts look right."
              : "Configure model and domain, test run, then run."}
          </p>
          <Input label="Model" value={dangerActive ? "account.move" : "res.partner"} readOnly />
          <div className="mt-3">
            <Textarea label="Domain (JSON list)" rows={2} value="[]" readOnly className="font-mono text-xs" />
          </div>
          <div className="po-actions">
            <Button type="button" variant="secondary" data-testid="power-ops-dry-run-btn">
              {DRY_RUN_CTA}
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={!canRun}
              data-testid="power-ops-run-btn"
            >
              {PRIMARY_CTA}
            </Button>
            {!canRun ? (
              <p className="po-primary-reason">
                Run recipe unlocks after a successful test run with the same recipe, model, and
                domain.
              </p>
            ) : null}
          </div>
        </section>
      ) : null}

      {state === "dry-run" || state === "executed" ? (
        <section className="po-panel" data-testid="power-ops-result-block">
          <h2 className="po-panel-title">
            {state === "dry-run" ? "Test run result" : "Run result"}
          </h2>
          <p className="po-result-label" data-testid="power-ops-result-label">
            {state === "dry-run"
              ? "Test run result (no writes)"
              : "Run result (writes applied)"}
          </p>
          <PowerOpsResultCounts
            {...(state === "dry-run" ? dryResult : liveResult)}
          />
          {partial ? (
            <PowerOpsStateGuide
              tone="warning"
              live
              testId="power-ops-partial-guide"
              guide={partial}
            />
          ) : null}
        </section>
      ) : null}
      </div>
    </div>
  );
}

export default function PowerOpsE2ePage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness…</main>}>
      <PowerOpsHarnessInner />
    </Suspense>
  );
}
