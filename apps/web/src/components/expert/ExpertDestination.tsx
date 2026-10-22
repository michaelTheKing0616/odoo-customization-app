"use client";

import { BuildSpineBar } from "@/components/build/BuildSpineBar";
import { PageHeader } from "@/components/ui/layout-primitives";
import {
  EXPERT_HONESTY_LINE,
  expertHeaderDescription,
  expertHonestyLegend,
} from "@/lib/expert-journey";
import { ExpertPanel } from "./ExpertPanel";
import { IntentRouterPanel } from "./IntentRouterPanel";

type ExpertDestinationProps = {
  connectionId: string;
  connectionName?: string | null;
};

/**
 * /connections/[id]/expert. The conversation is the page: the same `ExpertPanel` the drawer
 * uses, rendered inline. The side rail holds the router, the honesty legend and the build hand-off.
 */
export function ExpertDestination({ connectionId, connectionName }: ExpertDestinationProps) {
  return (
    <div className="expert-destination" data-testid="expert-destination">
      <PageHeader title="Odoo Expert" description={expertHeaderDescription(connectionName)} />
      <div className="studio-refinement expert-destination-grid">
        <section className="expert-destination-main" aria-label="Ask Odoo Expert">
          <ExpertPanel variant="page" />
        </section>
        <aside className="expert-rail" aria-label="Expert tools">
          <IntentRouterPanel connectionId={connectionId} variant="rail" />
          <section className="expert-rail-card" aria-labelledby="expert-limits-title" data-testid="expert-rail-honesty">
            <h2 className="expert-rail-title" id="expert-limits-title">
              What Expert will not do
            </h2>
            <p className="expert-honesty-line" data-testid="expert-overview-honesty">
              {EXPERT_HONESTY_LINE}
            </p>
            <ul className="expert-honesty-legend" data-testid="expert-overview-legend">
              {expertHonestyLegend().map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
          <details className="expert-rail-card expert-rail-spine" data-testid="expert-rail-spine">
            <summary className="expert-rail-summary">Build it in a studio</summary>
            <p className="expert-rail-note">
              Expert answers. A studio drafts and applies, with your confirmation.
            </p>
            <BuildSpineBar connectionId={connectionId} compact />
          </details>
        </aside>
      </div>
    </div>
  );
}
