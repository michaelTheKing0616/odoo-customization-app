"use client";

import { Suspense } from "react";
import { OperateStudioBar } from "@/components/operate-studio/OperateStudioBar";
import { useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/layout-primitives";
import { ConfigErrorNotice } from "@/components/config/ConfigErrorNotice";
import { ConfigStageRail } from "@/components/config/ConfigStageRail";
import { ConfigStateGuide } from "@/components/config/ConfigStateGuide";
import {
  APPLY_CTA,
  DRY_RUN_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  sanitizeConfigCopy,
  configSessionBadge,
  PRIMARY_CTA,
  appliedConfigGuide,
  configHonestyGuide,
  emptyConfigGuide,
  idleConfigGuide,
  planHonestyLabel,
  type ConfigStepIndex,
} from "@/lib/configScreen";
import "@/components/config/config-operate.css";

const STATES = [
  "empty",
  "idle",
  "configure",
  "dry-run",
  "settings",
  "applied",
  "error",
] as const;
type HarnessState = (typeof STATES)[number];

function stepFor(state: HarnessState): ConfigStepIndex {
  if (state === "empty" || state === "idle" || state === "error") return 1;
  if (state === "configure") return 2;
  if (state === "dry-run" || state === "settings") return 3;
  return 4;
}

function ConfigHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "idle";
  const state = (STATES.includes(raw as HarnessState) ? raw : "idle") as HarnessState;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const showHome = state === "empty" || state === "idle" || state === "error";
  const showDay1 = state === "configure" || state === "dry-run" || state === "applied";
  const showSettings = state === "settings";
  const canApply = state === "dry-run" || state === "settings" || state === "applied";
  const primaryLabel = showSettings ? PRIMARY_CTA : APPLY_CTA;

  return (
    <div
      className="config-operate op-studio-shell p-4 sm:p-6"
      data-testid="config-page"
      data-harness-state={state}
    >

      <header className="op-studio" data-testid="config-studio-chrome">
        <div className="op-titlebar">
          <div className="op-title-block">
            <p className="op-kicker">E2E mock connection</p>
            <h1 className="op-title">{PAGE_TITLE}</h1>
            <p className="op-subtitle">{PAGE_DESCRIPTION}</p>
          </div>
        </div>
        <OperateStudioBar
          testIdPrefix="config"
          badge={configSessionBadge(stepFor(state))}
          honesty={configHonestyGuide()}
          sanitize={sanitizeConfigCopy}
        />
        <ConfigStageRail step={stepFor(state)} />
      </header>

      <div className="op-desk">
        <div className="op-paper space-y-4">
      <div data-testid="config-command-center">

        {state === "error" ? (
          <ConfigErrorNotice
            className="mt-4"
            message="Connection timed out while loading recipes"
            context="load"
          />
        ) : null}

        {state === "empty" ? (
          <ConfigStateGuide
            tone="accent"
            density="brief" testId="config-empty-guide"
            guide={emptyConfigGuide()}
            actions={
              <Button type="button" variant="secondary" size="sm">
                Reload recipes
              </Button>
            }
          />
        ) : null}

        {state === "idle" ? (
          <ConfigStateGuide tone="accent" density="brief" testId="config-idle-guide" guide={idleConfigGuide()} />
        ) : null}

        {showHome && state !== "empty" && state !== "error" ? (
          <div className="cfg-recipe-grid mt-4">
            <div className="cfg-recipe" data-testid="recipe-card-day1">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="cfg-recipe-name">Day-1 setup</p>
                  <p className="cfg-recipe-desc">Company name, currency, country, language.</p>
                </div>
                <Badge variant="success">P0</Badge>
              </div>
              <div className="cfg-recipe-foot">
                <span className="text-xs text-muted">3 clicks</span>
                <Button type="button" size="sm" variant="secondary">
                  Open
                </Button>
              </div>
            </div>
            <div className="cfg-recipe" data-testid="recipe-card-settings-board">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="cfg-recipe-name">Settings board</p>
                  <p className="cfg-recipe-desc">Allowlisted res.config.settings.</p>
                </div>
                <Badge variant="info">P2</Badge>
              </div>
              <div className="cfg-recipe-foot">
                <span className="text-xs text-muted">Search then save</span>
                <Button type="button" size="sm" variant="secondary">
                  Open
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {showDay1 ? (
          <section className="cfg-panel" data-testid="day1-panel">
            <Button type="button" variant="ghost" size="sm">
              Back to Command Center
            </Button>
            <h2 className="cfg-panel-title mt-3">Day-1 setup</h2>
            <p className="cfg-panel-sub">
              Company name, currency, country, language. Test run then Apply.
            </p>
            <label className="mt-4 block text-sm">
              <span className="text-muted">Company name</span>
              <Input className="mt-1" defaultValue="Acme Trading" readOnly />
            </label>
            <div className="cfg-actions">
              <Button type="button" variant="secondary" data-testid="config-dry-run-btn">
                {DRY_RUN_CTA}
              </Button>
              <Button
                type="button"
                variant="primary"
                disabled={!canApply}
                data-testid="config-apply-btn"
              >
                {APPLY_CTA}
              </Button>
              {!canApply ? (
                <p className="cfg-primary-reason" data-testid="config-unlock-reason">
                  Apply unlocks after a successful test run with the same panel and values.
                </p>
              ) : null}
            </div>
            {state === "dry-run" || state === "applied" ? (
              <div
                className="mt-4"
                data-testid="recipe-plan-preview"
                data-dry-run={state === "dry-run" ? "true" : "false"}
              >
                <p className="cfg-result-label" data-testid="config-result-label">
                  {planHonestyLabel(state === "dry-run")}
                </p>
                <ul className="cfg-plan-steps">
                  <li>
                    <span className="font-mono text-ink">write_company</span>
                    {" · res.company.name - Rename"}
                  </li>
                </ul>
              </div>
            ) : null}
            {state === "applied" ? (
              <ConfigStateGuide
                className="mt-4"
                tone="accent"
                testId="config-applied-guide"
                guide={appliedConfigGuide("Day-1 setup")}
              />
            ) : null}
          </section>
        ) : null}

        {showSettings ? (
          <section className="cfg-panel" data-testid="settings-board-panel">
            <Button type="button" variant="ghost" size="sm">
              Back to Command Center
            </Button>
            <h2 className="cfg-panel-title mt-3">Settings board</h2>
            <p className="cfg-panel-sub">
              Allowlisted res.config.settings. Search, edit, test run, then {PRIMARY_CTA}.
            </p>
            <div className="cfg-settings-list">
              <label className="cfg-settings-row">
                <span className="font-mono text-xs text-ink">company_name</span>
                <Input className="max-w-[12rem]" defaultValue="Acme Trading" readOnly />
              </label>
            </div>
            <div className="cfg-actions">
              <Button type="button" variant="secondary" data-testid="config-dry-run-btn">
                {DRY_RUN_CTA}
              </Button>
              <Button
                type="button"
                variant="primary"
                data-testid="config-save-setting-btn"
              >
                {PRIMARY_CTA}
              </Button>
            </div>
            <div className="mt-4" data-testid="recipe-plan-preview" data-dry-run="true">
              <p className="cfg-result-label" data-testid="config-result-label">
                {planHonestyLabel(true)}
              </p>
            </div>
          </section>
        ) : null}
      </div>
        </div>
      </div>

    </div>
  );
}

export default function ConfigE2EPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness…</main>}>
      <ConfigHarnessInner />
    </Suspense>
  );
}
