"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";

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
  onCreateDraft: () => void;
  onApply: () => void;
  onDownloadZip: () => void;
  onOpenModuleSpec: () => void;
  onStashJobBrief: () => void;
};

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
  onCreateDraft,
  onApply,
  onDownloadZip,
  onOpenModuleSpec,
  onStashJobBrief,
}: DraftStudioApplyBarProps) {
  return (
    <div className="flex flex-wrap gap-2" data-testid="draft-studio-apply-bar">
      <Button
        type="button"
        variant="primary"
        disabled={aiBusy || !canDraft}
        loading={aiBusy}
        title={
          overlapPending
            ? "Resolve overlap findings first (Build anyway, Use, or Extend)"
            : needsConnectReview && !connectApproved
              ? "Review and approve connect points first"
              : undefined
        }
        onClick={onCreateDraft}
        data-testid="create-draft"
      >
        1. Create draft
      </Button>
      <Button
        type="button"
        variant={hasDraft && !moduleDelivery && !refuseClone && !stockReuse ? "primary" : "secondary"}
        disabled={
          !hasDraft || busy || !canApply || !finisherComplete || refuseClone || stockReuse
        }
        title={
          stockReuse
            ? "No custom ModuleSpec to apply — use Job Autopilot"
            : !finisherComplete
              ? "Wait for the Apps-store finisher (quality score) before applying"
              : (generateUiBlocked ?? undefined)
        }
        onClick={onApply}
        data-testid="apply-to-odoo"
      >
        {applied ? "Apply again" : "2. Apply to Odoo"}
      </Button>
      {stockReuse ? (
        <Link
          href={jobAutopilotHref}
          className="inline-flex items-center justify-center rounded-md bg-ink px-3 py-2 text-sm font-medium text-white"
          data-testid="open-job-autopilot"
          onClick={onStashJobBrief}
        >
          Open Job Autopilot
        </Link>
      ) : null}
      {hasDraft && !refuseClone && !stockReuse ? (
        <Button
          type="button"
          variant={moduleDelivery ? "primary" : "secondary"}
          disabled={zipBusy || !finisherComplete || zipLocked}
          loading={zipBusy}
          data-testid="download-module-zip"
          title={zipLocked ? "Authoring gate has not passed — zip stays locked" : undefined}
          onClick={onDownloadZip}
        >
          {moduleDelivery ? "Download module zip" : "Download zip"}
        </Button>
      ) : null}
      <Button
        type="button"
        variant="secondary"
        disabled={!hasDraft || stockReuse}
        data-testid="open-modulespec"
        onClick={onOpenModuleSpec}
      >
        Open ModuleSpec
      </Button>
      {hasDraft && !refuseClone && !stockReuse ? (
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
    </div>
  );
}
