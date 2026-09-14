"use client";

import { Button } from "@/components/ui/Button";
import {
  isProjectArchived,
  type ProjectRow,
  type ProjectsBusy,
} from "@/lib/projects-journey";

type ProjectApplyBarProps = {
  project: ProjectRow;
  busy: ProjectsBusy;
  canMutate: boolean;
  canApply: boolean;
  applyBlocked?: string | null;
  mutateBlocked?: string | null;
  hasDiff?: boolean;
  onReview: () => void;
  onApply: () => void;
  onArchive: () => void;
};

export function ProjectApplyBar({
  project,
  busy,
  canMutate,
  canApply,
  applyBlocked,
  mutateBlocked,
  hasDiff,
  onReview,
  onApply,
  onArchive,
}: ProjectApplyBarProps) {
  const working = busy !== null;
  const archived = isProjectArchived(project);
  return (
    <div className="flex flex-wrap gap-2" data-testid="projects-apply-bar">
      <Button
        type="button"
        variant={hasDiff ? "ghost" : "secondary"}
        size="sm"
        disabled={working || !canMutate}
        title={mutateBlocked ?? undefined}
        loading={busy === "diff"}
        onClick={onReview}
        data-testid="projects-review"
      >
        Review vs live
      </Button>
      <Button
        type="button"
        variant="primary"
        size="sm"
        disabled={working || !canApply || archived}
        title={archived ? "Un-archive this draft before Apply" : (applyBlocked ?? undefined)}
        loading={busy === "apply"}
        onClick={onApply}
        data-testid="projects-apply"
      >
        Apply
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={working}
        loading={busy === "archive"}
        onClick={onArchive}
        data-testid="projects-archive"
      >
        {archived ? "Un-archive" : "Archive"}
      </Button>
    </div>
  );
}
