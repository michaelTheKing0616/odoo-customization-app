"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/layout-primitives";
import { StudioStageRail } from "./StudioStageRail";
import type { StudioJourneyState } from "@/lib/studio-journey";

type StudioShellProps = {
  connectionId: string;
  journey: StudioJourneyState;
  canvas?: boolean;
  hasSession?: boolean;
  onStartNew?: () => void;
  children: React.ReactNode;
};

export function StudioShell({
  connectionId,
  journey,
  canvas,
  hasSession,
  onStartNew,
  children,
}: StudioShellProps) {
  return (
    <div className="studio-refinement" data-testid="studio-page">
      <div className={`studio-page${canvas ? " is-canvas" : ""}`}>
        <PageHeader
          title="App Studio"
          description="Describe a change in plain words, check the form preview, then apply it to Odoo when you're ready."
          actions={
            <>
              {hasSession && onStartNew ? (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={onStartNew}
                  data-testid="studio-start-new"
                >
                  Start new app
                </Button>
              ) : null}
              <Link
                href={`/connections/${connectionId}/wireframe`}
                className="text-ui-body text-muted hover:text-ink"
                data-testid="studio-wireframe-link"
              >
                Upload sketch
              </Link>
              <Link
                href={`/connections/${connectionId}/wizard`}
                className="text-ui-body text-muted hover:text-ink"
                data-testid="studio-power-worksheet"
              >
                Worksheet
              </Link>
            </>
          }
        />
        <StudioStageRail journey={journey} />
        {children}
      </div>
    </div>
  );
}
