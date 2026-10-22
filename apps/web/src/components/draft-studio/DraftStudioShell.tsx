"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/layout-primitives";
import { DraftStudioStageRail } from "./DraftStudioStageRail";
import type { DraftStudioJourneyState } from "@/lib/draft-studio-journey";
import { BuildSpineBar } from "@/components/build/BuildSpineBar";
import { useBuildSpineHandoff } from "@/lib/use-build-spine-handoff";

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
  const handoff = useBuildSpineHandoff(connectionId);
  return (
    <div className="studio-refinement" data-testid="draft-studio">
      <div className={`studio-page${canvas ? " is-canvas" : ""}`}>
        <PageHeader
          title="Draft Studio"
          description={
            connectionName
              ? `${connectionName} · draft an app plan, review the scorecard, apply when you mean it`
              : "Draft an app plan. Review draft completeness, quality checks, and Autopilot separately. Apply when you mean it."
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
                className="draft-studio-header-link"
              >
                App Studio
              </Link>
            </>
          }
        />
        <div
          className="draft-studio-ia-banner"
          data-testid="draft-studio-ia-banner"
        >
          <p className="draft-studio-ia-banner-body">
            Draft Studio is a power worksheet of{" "}
            <Link
              href={`/connections/${connectionId}/studio`}
              className="font-medium text-ink underline underline-offset-2"
            >
              App Studio
            </Link>
            . Existing drafts stay safe. Prefer App Studio for new work, or{" "}
            <Link
              href={`/connections/${connectionId}/projects`}
              className="font-medium text-ink underline underline-offset-2"
            >
              Projects
            </Link>{" "}
            to track them.
          </p>
        </div>
        <DraftStudioStageRail journey={journey} />
        <details
          className="draft-studio-disclosure draft-studio-spine"
          open={handoff ? true : undefined}
          data-testid="draft-studio-spine"
        >
          <summary>
            <span>Switch build mode</span>
            <span className="draft-studio-disclosure-meta">Residual app</span>
          </summary>
          <div className="mt-3">
            <BuildSpineBar
              connectionId={connectionId}
              activeMode="residual_app"
              handoff={handoff}
              compact
            />
          </div>
        </details>
        {children}
      </div>
    </div>
  );
}
