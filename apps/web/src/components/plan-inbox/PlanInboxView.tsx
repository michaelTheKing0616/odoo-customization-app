"use client";

import type { FormEvent, KeyboardEvent, ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/layout-primitives";
import { ListLayout, ListLayoutItem } from "@/components/ui/motion";
import {
  CONNECTION_LABEL,
  OPEN_INBOX_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PLAN_STATUS_META,
  REFRESH_CTA,
  countActionable,
  emptyInboxGuide,
  environmentLabel,
  expiryPhrase,
  isActionable,
  loadErrorGuide,
  noConnectionGuide,
  notFoundGuide,
  planDisplayStatus,
  shortFingerprint,
  sortPlans,
  type InboxPlanCard,
  type PlanDecision,
} from "@/lib/planInboxScreen";
import { PlanInboxStateGuide } from "./PlanInboxStateGuide";
import { PlanLedger, type PlanDecisionState } from "./PlanLedger";
import { PlanPaper } from "./PlanPaper";
import { FrameMeta } from "@/components/frame/FrameMeta";
import { AllClear } from "@/components/ui/craft";

export type PlanInboxPhase = "idle" | "loading" | "ready" | "error";

export type PlanInboxViewProps = {
  connectionId: string;
  onConnectionChange: (value: string) => void;
  onOpen: () => void;
  onRefresh: () => void;
  phase: PlanInboxPhase;
  plans: InboxPlanCard[];
  loadedConnectionId: string;
  selectedHash: string | null;
  /** A plan id from the URL that is not in the list renders "not found". */
  missingHash?: string | null;
  onSelect: (hash: string) => void;
  viewerId: string | null;
  staleHashes?: ReadonlySet<string>;
  decision: PlanDecisionState;
  onDecide: (plan: InboxPlanCard, decision: PlanDecision) => void;
  now: Date;
  timeZone?: string;
  initialConfirm?: PlanDecision | null;
};

/** UI-S-50 plan inbox: basalt bar, plan rail, paper canvas, approval inspector. */
/** A faint plan sheet behind state notes, so an empty canvas still reads as the document desk. */
function SheetStage({ children }: { children: ReactNode }) {
  return (
    <div className="pi-sheet-stage">
      <div className="pi-ghost" aria-hidden>
        <span className="pi-ghost-bar" style={{ width: "22%" }} />
        <span className="pi-ghost-bar pi-ghost-title" style={{ width: "68%" }} />
        <span className="pi-ghost-meta">
          <span className="pi-ghost-bar" />
          <span className="pi-ghost-bar" />
          <span className="pi-ghost-bar" />
          <span className="pi-ghost-bar" />
        </span>
        {[72, 58, 64, 46, 54].map((width, i) => (
          <span key={i} className="pi-ghost-row">
            <span className="pi-ghost-index">{String(i + 1).padStart(2, "0")}</span>
            <span className="pi-ghost-lines">
              <span className="pi-ghost-bar" style={{ width: "28%" }} />
              <span className="pi-ghost-bar" style={{ width: `${width}%` }} />
              <span className="pi-ghost-bar" style={{ width: `${width - 14}%` }} />
            </span>
          </span>
        ))}
      </div>
      <div className="pi-sheet-note">{children}</div>
    </div>
  );
}

export function PlanInboxView({
  connectionId,
  onConnectionChange,
  onOpen,
  onRefresh,
  phase,
  plans,
  loadedConnectionId,
  selectedHash,
  missingHash = null,
  onSelect,
  viewerId,
  staleHashes,
  decision,
  onDecide,
  now,
  timeZone,
  initialConfirm = null,
}: PlanInboxViewProps) {
  const ordered = sortPlans(plans, now);
  const waiting = countActionable(plans, now);
  const open = ordered.filter((plan) => isActionable(plan, now));
  const closed = ordered.filter((plan) => !isActionable(plan, now));
  const showWorkspace = phase === "ready" && plans.length > 0;
  const selected = missingHash ? null : (ordered.find((plan) => plan.plan_hash === selectedHash) ?? null);
  const selectedStatus = selected
    ? planDisplayStatus(selected, now, { stale: staleHashes?.has(selected.plan_hash) })
    : null;

  /** On stacked layouts the paper sits under the rail: move focus and view to it after a pick. */
  function pick(hash: string) {
    onSelect(hash);
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    if (!window.matchMedia("(max-width: 1023px)").matches) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.requestAnimationFrame(() => {
      const heading = document.getElementById("pi-card-title");
      heading?.scrollIntoView({ block: "start", behavior: reduced ? "auto" : "smooth" });
      heading?.focus({ preventScroll: true });
    });
  }

  /** Arrow keys walk the rail like a mail list. Keyboard moves never animate. */
  function onRailKey(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const rows = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button.pi-row"));
    const at = rows.findIndex((row) => row === document.activeElement);
    if (at === -1) return;
    event.preventDefault();
    const next = rows[Math.min(rows.length - 1, Math.max(0, at + (event.key === "ArrowDown" ? 1 : -1)))];
    next.focus();
    const hash = next.dataset.hash;
    if (hash) onSelect(hash);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onOpen();
  }

  function renderRow(plan: InboxPlanCard, index: number) {
    const status = planDisplayStatus(plan, now, { stale: staleHashes?.has(plan.plan_hash) });
    const meta = PLAN_STATUS_META[status];
    const isSelected = selected?.plan_hash === plan.plan_hash;
    return (
      <ListLayoutItem key={plan.plan_hash} index={index} className="pi-row-item">
        <button
          type="button"
          className="pi-row"
          data-selected={isSelected ? "true" : "false"}
          data-status={status}
          data-hash={plan.plan_hash}
          aria-current={isSelected ? "true" : undefined}
          onClick={() => pick(plan.plan_hash)}
          data-testid="plan-inbox-row"
        >
          <span className="pi-risk" data-risk={plan.max_risk}>
            {plan.max_risk}
          </span>
          <span className="pi-row-main">
            <span className="pi-row-goal">{plan.goal}</span>
            <span className="pi-row-meta">
              <span className="pi-status" data-tone={meta.tone}>
                {meta.label}
              </span>
              <span className="pi-row-env">{environmentLabel(plan.environment)}</span>
            </span>
            <span className="pi-row-foot">
              <code translate="no">{shortFingerprint(plan.plan_hash)}</code>
              <span>{expiryPhrase(plan, now)}</span>
            </span>
          </span>
        </button>
      </ListLayoutItem>
    );
  }

  return (
    <main
      className="plan-inbox-operate"
      data-testid="approvals-inbox-page"
      data-phase={phase}
      aria-busy={phase === "loading"}
    >
      <header className="pi-bar">
        <div className="pi-bar-id">
          <FrameMeta />
          <h1 className="pi-bar-title">{PAGE_TITLE}</h1>
          <p className="pi-bar-lead" data-testid="plan-inbox-lead">
            {PAGE_DESCRIPTION}
          </p>
        </div>
        <form className="pi-bar-form" onSubmit={submit} data-testid="plan-inbox-connection-form">
          <label htmlFor="plan-inbox-connection" className="pi-bar-label">
            {CONNECTION_LABEL}
          </label>
          <input
            id="plan-inbox-connection"
            className="pi-bar-input"
            value={connectionId}
            onChange={(event) => onConnectionChange(event.target.value)}
            placeholder="conn-…"
            autoComplete="off"
            spellCheck={false}
            required
          />
          <Button
            type="submit"
            size="sm"
            variant={showWorkspace ? "secondary" : "primary"}
            loading={phase === "loading"}
            className="pi-bar-btn"
          >
            {OPEN_INBOX_CTA}
          </Button>
        </form>
      </header>

      {phase === "idle" ? (
        <div className="pi-canvas pi-canvas-solo">
          <SheetStage>
            <PlanInboxStateGuide guide={noConnectionGuide()} variant="sheet" testId="plan-inbox-idle" />
          </SheetStage>
        </div>
      ) : null}

      {phase === "loading" ? (
        <div className="pi-workspace" data-testid="approvals-inbox-loading">
          <div className="pi-rail">
            <div className="pi-skeleton-stack">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          </div>
          <div className="pi-canvas">
            <div className="pi-paper pi-skeleton-stack pi-paper-skeleton">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-7 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
            </div>
          </div>
          <div className="pi-ledger pi-skeleton-stack">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        </div>
      ) : null}

      {phase === "error" ? (
        <div className="pi-canvas pi-canvas-solo">
          <SheetStage>
              <PlanInboxStateGuide
              guide={loadErrorGuide()}
              tone="danger"
              variant="sheet"
              live="alert"
              testId="plan-inbox-error"
              actions={
                <Button type="button" variant="secondary" size="sm" onClick={onRefresh}>
                  {REFRESH_CTA}
                </Button>
              }
            />
          </SheetStage>
        </div>
      ) : null}

      {phase === "ready" && plans.length === 0 ? (
        <div className="pi-canvas pi-canvas-solo">
          <SheetStage>
            <AllClear title="Nothing is waiting for you." checkedAt={new Date()} />
              <PlanInboxStateGuide
              guide={emptyInboxGuide(loadedConnectionId)}
              variant="sheet"
              testId="plan-inbox-empty"
              actions={
                <Button type="button" variant="secondary" size="sm" onClick={onRefresh}>
                  {REFRESH_CTA}
                </Button>
              }
            />
          </SheetStage>
        </div>
      ) : null}

      {showWorkspace ? (
        <div className="pi-workspace" data-has-ledger={selected ? "true" : "false"}>
          <nav className="pi-rail" aria-labelledby="pi-rail-title" data-testid="plan-inbox-list" onKeyDown={onRailKey}>
            <div className="pi-rail-head">
              <h2 id="pi-rail-title" className="pi-rail-title">
                Plans
              </h2>
              <p className="pi-rail-count" data-testid="plan-inbox-count">
                <span className="pi-num">{waiting}</span> waiting of <span className="pi-num">{plans.length}</span>
              </p>
            </div>
            <p className="pi-rail-scope" translate="no">
              {loadedConnectionId}
            </p>
            {open.length > 0 ? (
              <>
                <p className="pi-rail-group">Waiting</p>
                <ListLayout stagger={false} className="pi-rows">
                  {open.map((plan, index) => renderRow(plan, index))}
                </ListLayout>
              </>
            ) : null}
            {closed.length > 0 ? (
              <>
                <p className="pi-rail-group">Closed</p>
                <ListLayout stagger={false} className="pi-rows">
                  {closed.map((plan, index) => renderRow(plan, open.length + index))}
                </ListLayout>
              </>
            ) : null}
          </nav>

          <div className="pi-canvas">
            {missingHash ? (
              <PlanInboxStateGuide guide={notFoundGuide(missingHash)} variant="sheet" testId="plan-inbox-not-found" />
            ) : selected && selectedStatus ? (
              <PlanPaper plan={selected} status={selectedStatus} now={now} timeZone={timeZone} />
            ) : (
              <p className="pi-canvas-hint">Pick a plan from the list to read its card.</p>
            )}
          </div>

          {selected && selectedStatus ? (
            <PlanLedger
              key={selected.plan_hash}
              plan={selected}
              status={selectedStatus}
              now={now}
              viewerId={viewerId}
              decision={decision}
              onDecide={onDecide}
              onRefresh={onRefresh}
              initialConfirm={initialConfirm}
            />
          ) : null}
        </div>
      ) : null}
    </main>
  );
}
