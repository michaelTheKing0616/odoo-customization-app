"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { OpsHubStateGuide } from "@/components/operations/OpsHubStateGuide";
import { OpsHubToolGroups } from "@/components/operations/OpsHubToolGroups";
import {
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  featuredTool,
  opsHubHonestyGuide,
  pickToolGuide,
  sanitizeOpsHubCopy,
} from "@/lib/operationsHubScreen";
import "@/components/operations/operations-operate.css";
import { FrameMeta } from "@/components/frame/FrameMeta";

type OpsHubPageViewProps = {
  connectionId: string;
  /** Optional harness marker */
  harnessState?: string;
};

export function OpsHubPageView({ connectionId, harnessState }: OpsHubPageViewProps) {
  const base = `/connections/${connectionId}`;
  const featured = featuredTool();
  const pick = pickToolGuide();
  const honesty = opsHubHonestyGuide();

  return (
    <div
      className="ops-hub-operate"
      data-testid="operations-hub"
      data-harness-state={harnessState || undefined}
    >
      <div className="oh-desk">
        <article className="oh-sheet">
          <header className="oh-masthead studio-bar-dark">
            <div className="oh-mast-copy">
              <FrameMeta />
              <h1 className="oh-title">{PAGE_TITLE}</h1>
              <p className="oh-lead" data-testid="ops-hub-pick-guide">
                <span className="oh-lead-title" data-testid="ops-hub-pick-guide-title">
                  {sanitizeOpsHubCopy(pick.title)}
                </span>
                <span className="oh-lead-body" data-testid="ops-hub-pick-guide-why">
                  {sanitizeOpsHubCopy(pick.why)}
                </span>
                <span className="oh-lead-next" data-testid="ops-hub-pick-guide-next">
                  {sanitizeOpsHubCopy(pick.next)}
                </span>
              </p>
              <p className="oh-scope">{sanitizeOpsHubCopy(PAGE_DESCRIPTION)}</p>
            </div>
            <div className="oh-mast-actions">
              <Button asChild variant="primary" size="sm">
                <Link href={`${base}/${featured.href}`} data-testid="ops-hub-primary-cta">
                  {PRIMARY_CTA}
                </Link>
              </Button>
            </div>
          </header>

          <OpsHubToolGroups base={base} />

          {/* Honesty only beside write tools: risk is imminent when choosing a write path. */}
          <OpsHubStateGuide
            density="caption"
            tone="warning"
            testId="ops-hub-honesty"
            guide={honesty}
          />
        </article>
      </div>
    </div>
  );
}
