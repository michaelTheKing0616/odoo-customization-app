"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import {
  DENY_CTA,
  PRIMARY_CTA,
  SIGN_OFF_NOTE,
  STOP_CTA,
  approveGate,
  approverSlots,
  blockerLines,
  confirmCopy,
  riskCaution,
  statusGuide,
  timelineSteps,
  type DecideFailure,
  type InboxPlanCard,
  type PlanDecision,
  type PlanDisplayStatus,
} from "@/lib/planInboxScreen";
import { PlanInboxStateGuide } from "./PlanInboxStateGuide";

export type PlanDecisionState = {
  busy: PlanDecision | null;
  message: string | null;
  failure: DecideFailure | null;
};

type PlanLedgerProps = {
  plan: InboxPlanCard;
  status: PlanDisplayStatus;
  now: Date;
  viewerId: string | null;
  decision: PlanDecisionState;
  onDecide: (plan: InboxPlanCard, decision: PlanDecision) => void;
  onRefresh: () => void;
  /** Harness only: open the inline confirm on first render. */
  initialConfirm?: PlanDecision | null;
};

const STEP_SUFFIX = { done: "done", current: "current step", todo: "not started", blocked: "closed" } as const;

/** Basalt inspector: where the plan is, who has signed, and the one decision. */
export function PlanLedger({
  plan,
  status,
  now,
  viewerId,
  decision,
  onDecide,
  onRefresh,
  initialConfirm = null,
}: PlanLedgerProps) {
  const [confirm, setConfirm] = useState<PlanDecision | null>(initialConfirm);
  useEffect(() => {
    setConfirm(initialConfirm);
  }, [plan.plan_hash, initialConfirm]);
  useEffect(() => {
    if (decision.message || decision.failure) setConfirm(null);
  }, [decision.message, decision.failure]);

  const stale = status === "stale";
  const guide = statusGuide(plan, status, now);
  const gate = approveGate(plan, now, viewerId, { stale });
  const slots = approverSlots(plan);
  const blockers = blockerLines(plan);
  const caution = riskCaution(plan, status);
  const steps = timelineSteps(plan, status);
  const pending = status === "pending";
  const canDeny = pending && Boolean(viewerId) && Boolean(plan.schema_fp);
  const busy = decision.busy !== null;
  const confirmText = confirm ? confirmCopy(plan, confirm, now) : null;
  const showFailure =
    decision.failure !== null && !(decision.failure.kind === "stale" && status === "stale");

  return (
    <aside className="pi-ledger" aria-labelledby="pi-ledger-title" data-testid="plan-card-decide">
      <div className="pi-ledger-section">
        <h2 id="pi-ledger-title" className="pi-ledger-title">
          Approval
        </h2>
        <ol className="pi-timeline" data-testid="plan-inbox-stage-rail" aria-label="Where this plan is">
          {steps.map((step, i) => (
            <li
              key={step.label}
              className="pi-timeline-step"
              data-state={step.state}
              aria-current={step.state === "current" ? "step" : undefined}
              data-testid={`plan-inbox-step-${i + 1}`}
            >
              <span className="pi-timeline-dot" aria-hidden />
              <span className="pi-timeline-label">
                {step.label}
                <span className="sr-only">, {STEP_SUFFIX[step.state]}</span>
              </span>
              <span className="pi-timeline-detail">{step.detail}</span>
            </li>
          ))}
        </ol>
      </div>

      <div className="pi-ledger-section">
        <p className="pi-ledger-label">
          {slots.needed === 0
            ? "No signature required by policy"
            : slots.needed === 1
              ? "Signature"
              : `Signatures, ${slots.needed} different people`}
        </p>
        {slots.slots.length > 0 ? (
          <ul className="pi-sigs" data-testid="plan-card-slots">
            {slots.slots.map((slot) => (
              <li
                key={slot.index}
                className="pi-sig"
                data-filled={slot.person ? "true" : "false"}
                data-testid="plan-card-slot"
              >
                <span className="pi-sig-name" translate="no">
                  {slot.person ? (slot.person === viewerId ? `${slot.person} (you)` : slot.person) : "Open"}
                </span>
                <span className="pi-sig-line" aria-hidden />
                <span className="pi-sig-caption">
                  Approver {slot.index}
                  {slot.person ? ", signed" : ""}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
        {slots.distinctRequired ? (
          <p className="pi-ledger-fine" data-testid="plan-card-distinct-note">
            The second approver must be a different person from the first.
          </p>
        ) : null}
      </div>

      {caution ? (
        <PlanInboxStateGuide guide={caution} tone="warning" testId="plan-card-caution" />
      ) : null}

      {blockers.length > 0 ? (
        <div className="pi-ledger-section" data-testid="plan-card-blockers">
          <p className="pi-ledger-label">Still blocking approval</p>
          <ul className="pi-blockers">
            {blockers.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {guide ? (
        <PlanInboxStateGuide
          guide={guide}
          tone={status === "approved" ? "success" : status === "stale" || status === "expired" ? "warning" : status === "blocked" ? "danger" : "neutral"}
          testId="plan-card-status-guide"
          actions={
            status === "stale" || status === "voided" ? (
              <Button type="button" variant="secondary" size="sm" onClick={onRefresh}>
                Refresh inbox
              </Button>
            ) : undefined
          }
        />
      ) : null}

      {pending && !gate.allowed && gate.reason ? (
        <PlanInboxStateGuide guide={gate.reason} tone="neutral" testId="plan-card-gate" />
      ) : null}

      {pending ? (
        <div className="pi-ledger-decide">
          {confirm && confirmText ? (
            <div className="pi-confirm" data-testid="plan-card-confirm" data-decision={confirm}>
              <p className="pi-confirm-title">{confirmText.title}</p>
              <p className="pi-confirm-body">{confirmText.body}</p>
              <div className="pi-actions">
                <Button
                  type="button"
                  variant={confirm === "approve" ? "primary" : "secondary"}
                  loading={decision.busy === confirm}
                  disabled={busy}
                  onClick={() => onDecide(plan, confirm)}
                  data-testid="plan-card-confirm-cta"
                >
                  {decision.busy === confirm ? (confirm === "approve" ? "Approving…" : "Denying…") : confirmText.cta}
                </Button>
                <Button type="button" variant="ghost" disabled={busy} onClick={() => setConfirm(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="pi-actions" data-testid="plan-card-actions">
              <Button
                type="button"
                variant="primary"
                disabled={!gate.allowed || busy}
                onClick={() => setConfirm("approve")}
                data-testid="plan-card-approve"
              >
                {PRIMARY_CTA}
              </Button>
              <div className="pi-actions-row">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!canDeny || busy}
                  onClick={() => setConfirm("deny")}
                  data-testid="plan-card-deny"
                >
                  {DENY_CTA}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  disabled={!canDeny || busy}
                  onClick={() => setConfirm("deny_and_stop")}
                  data-testid="plan-card-stop"
                >
                  {STOP_CTA}
                </Button>
              </div>
            </div>
          )}
          <p className="pi-ledger-fine" data-testid="plan-card-signoff-note">
            {SIGN_OFF_NOTE}
          </p>
        </div>
      ) : null}

      <p
        className="pi-live"
        data-echo={guide ? "true" : undefined}
        role="status"
        aria-live="polite"
        data-testid="plan-card-result"
      >
        {decision.message ?? ""}
      </p>
      {showFailure && decision.failure ? (
        <PlanInboxStateGuide
          guide={decision.failure.guide}
          tone={decision.failure.kind === "stale" || decision.failure.kind === "frozen" ? "warning" : "danger"}
          testId="plan-card-failure"
          live="alert"
          actions={
            <Button type="button" variant="secondary" size="sm" onClick={onRefresh}>
              Refresh inbox
            </Button>
          }
        />
      ) : null}
    </aside>
  );
}
