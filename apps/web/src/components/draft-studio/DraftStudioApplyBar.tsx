"use client";

import Link from "next/link";
import { useId } from "react";
import { Button } from "@/components/ui/Button";
import {
  applyBlockedReason,
  generateBlockedReason,
  wizardPrimaryAction,
} from "@/lib/wizard-ui";

type DraftStudioApplyBarProps = {
  canDraft: boolean;
  canApply: boolean;
  hasDraft: boolean;
  aiBusy: boolean;
  busy: boolean;
  zipBusy: boolean;
  finisherComplete: boolean;
  refuseClone: boolean;
  stockReuse: boolean;
  moduleDelivery: boolean;
  zipLocked: boolean;
  generateUiBlocked: string | null;
  overlapPending: boolean;
  needsConnectReview: boolean;
  connectApproved: boolean;
  designerHref: string;
  designerModel: string | null;
  jobAutopilotHref: string;
  applied: boolean;
  /** Prompt length, so the disabled reason can say what is missing. Optional for harnesses. */
  promptLength?: number;
  onCreateDraft: () => void;
  onApply: () => void;
  onDownloadZip: () => void;
  onOpenModuleSpec: () => void;
  onStashJobBrief: () => void;
};

/**
 * Stage-aware action bar. Prompt stage: one filled action, "Generate the draft".
 * Review stage: one filled action (Apply, module zip, or Job Autopilot), the rest
 * secondary. A disabled primary always says why, in visible text.
 */
export function DraftStudioApplyBar({
  canDraft,
  canApply,
  hasDraft,
  aiBusy,
  busy,
  zipBusy,
  finisherComplete,
  refuseClone,
  stockReuse,
  moduleDelivery,
  zipLocked,
  generateUiBlocked,
  overlapPending,
  needsConnectReview,
  connectApproved,
  designerHref,
  designerModel,
  jobAutopilotHref,
  applied,
  promptLength,
  onCreateDraft,
  onApply,
  onDownloadZip,
  onOpenModuleSpec,
  onStashJobBrief,
}: DraftStudioApplyBarProps) {
  const reasonId = useId();
  const primary = wizardPrimaryAction({ hasDraft, stockReuse, refuseClone, moduleDelivery });

  if (!hasDraft) {
    const reason = canDraft
      ? null
      : generateBlockedReason({
          promptLength: promptLength ?? (overlapPending || needsConnectReview ? 3 : 0),
          aiBusy,
          overlapPending,
          needsConnectReview,
          connectApproved,
        });
    return (
      <div
        className="draft-studio-apply-bar"
        data-testid="draft-studio-apply-bar"
        data-stage="prompt"
      >
        <div className="draft-studio-apply-row">
          <Button
            type="button"
            variant="primary"
            className="draft-studio-primary-cta"
            disabled={aiBusy || !canDraft}
            loading={aiBusy}
            aria-describedby={reason ? reasonId : undefined}
            onClick={onCreateDraft}
            data-testid="create-draft"
          >
            Generate the draft
          </Button>
        </div>
        {reason ? (
          <p id={reasonId} className="draft-studio-apply-reason" data-testid="create-draft-reason">
            {reason}
          </p>
        ) : null}
      </div>
    );
  }

  const applyDisabled =
    busy || !canApply || !finisherComplete || refuseClone || stockReuse;
  const applyReason = applyBlockedReason({
    hasDraft,
    busy,
    canApply,
    finisherComplete,
    refuseClone,
    stockReuse,
    generateUiBlocked,
  });
  const showModuleActions = !refuseClone && !stockReuse;

  return (
    <div className="draft-studio-apply-bar" data-testid="draft-studio-apply-bar" data-stage="review">
      <div className="draft-studio-apply-row">
        <Button
          type="button"
          variant="secondary"
          disabled={aiBusy || !canDraft}
          loading={aiBusy}
          title={
            overlapPending
              ? "Resolve overlap findings first (Build anyway, Use, or Extend)"
              : needsConnectReview && !connectApproved
                ? "Review and approve connect points first"
                : "Replaces this draft. Nothing writes to Odoo."
          }
          onClick={onCreateDraft}
          data-testid="create-draft"
        >
          Regenerate the draft
        </Button>
        {showModuleActions ? (
          <Button
            type="button"
            variant="secondary"
            data-testid="open-modulespec"
            onClick={onOpenModuleSpec}
          >
            Open ModuleSpec
          </Button>
        ) : null}
        {showModuleActions ? (
          <Button variant="secondary" asChild>
            <Link
              href={designerHref}
              data-testid="open-view-designer"
              title={
                designerModel
                  ? `Opens View Designer on ${designerModel}. Apply to Odoo first so the form exists on this connection.`
                  : "Opens View Designer. Apply to Odoo first so views exist on this connection."
              }
            >
              Open View Designer
            </Link>
          </Button>
        ) : null}
        {showModuleActions ? (
          <Button
            type="button"
            variant={primary === "zip" ? "primary" : "secondary"}
            disabled={zipBusy || !finisherComplete || zipLocked}
            loading={zipBusy}
            data-testid="download-module-zip"
            title={zipLocked ? "Authoring gate has not passed. Zip stays locked" : undefined}
            onClick={onDownloadZip}
          >
            {moduleDelivery ? "Download module zip" : "Download zip"}
          </Button>
        ) : null}
        {showModuleActions ? (
          <Button
            type="button"
            variant={primary === "apply" && !applied ? "primary" : "secondary"}
            className={primary === "apply" && !applied ? "draft-studio-primary-cta" : undefined}
            disabled={applyDisabled}
            aria-describedby={applyReason ? reasonId : undefined}
            title={applyReason ?? undefined}
            onClick={onApply}
            data-testid="apply-to-odoo"
          >
            {applied ? "Apply again" : "Apply to Odoo"}
          </Button>
        ) : null}
        {stockReuse ? (
          <Button asChild variant="primary" className="draft-studio-primary-cta">
            <Link
              href={jobAutopilotHref}
              data-testid="open-job-autopilot"
              onClick={onStashJobBrief}
            >
              Open Job Autopilot
            </Link>
          </Button>
        ) : null}
      </div>
      {applyReason ? (
        <p id={reasonId} className="draft-studio-apply-reason" data-testid="apply-to-odoo-reason">
          {applyReason}
        </p>
      ) : null}
    </div>
  );
}
