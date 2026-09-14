"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/layout-primitives";
import { DraftStudioStageRail } from "./DraftStudioStageRail";
import type { DraftStudioJourneyState } from "@/lib/draft-studio-journey";

type DraftStudioShellProps = {
  connectionId: string;
  connectionName?: string;
  journey: DraftStudioJourneyState;
  canvas?: boolean;
  hasDraft?: boolean;
  onStartNew?: () => void;
  children: React.ReactNode;
};

export function DraftStudioShell({
  connectionId,
  connectionName,
  journey,
  canvas,
  hasDraft,
  onStartNew,
  children,
}: DraftStudioShellProps) {
  return (
    <div className="studio-refinement" data-testid="draft-studio">
      <div className={`studio-page${canvas ? " is-canvas" : ""}`}>
        <PageHeader
          title="Draft Studio"
          description={
            connectionName
              ? `${connectionName} · describe a field, a feature, or a full app — then apply it to Odoo`
              : "Describe a field, a feature, or a full app. Review the scorecard. Apply only when you mean it."
          }
          actions={
            <>
              {hasDraft && onStartNew ? (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={onStartNew}
                  data-testid="draft-studio-start-new"
                >
                  Start new draft
                </Button>
              ) : null}
              <Link
                href={`/connections/${connectionId}/studio`}
                className="text-sm text-muted hover:text-ink"
              >
                App Studio
              </Link>
            </>
          }
        />
        <DraftStudioStageRail journey={journey} />
        {children}
      </div>
    </div>
  );
}
