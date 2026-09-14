"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";

type ModuleSpecHandoffBarProps = {
  connectionId: string;
  designerHref: string;
  designerModel: string | null;
  projectId?: string | null;
  stockReuse?: boolean;
  applied?: boolean;
  odooAppUrl?: string | null;
};

export function ModuleSpecHandoffBar({
  connectionId,
  designerHref,
  designerModel,
  projectId,
  stockReuse,
  applied,
  odooAppUrl,
}: ModuleSpecHandoffBarProps) {
  const projectsHref = projectId
    ? `/connections/${connectionId}/projects?project=${encodeURIComponent(projectId)}`
    : `/connections/${connectionId}/projects`;
  return (
    <Card className="p-5" data-testid="modulespec-handoff-bar">
      <h2 className="text-lg font-semibold text-ink">Open related surfaces</h2>
      <p className="mt-1 text-sm text-muted">
        ModuleSpec is the IR. Draft Studio authors it. Projects version the draft.
        View Designer edits live forms. Job Autopilot is the sandbox done-bar — not Completeness 10.0.
        Promote stays human.
      </p>
      <div className="job-handoff-bar mt-4">
        <Button asChild variant="ghost" size="sm">
          <Link href={`/connections/${connectionId}/wizard`}>Draft Studio</Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link
            href={designerHref}
            data-testid="modulespec-open-designer"
            title={
              designerModel
                ? `Opens View Designer on ${designerModel}. Apply first so the form exists on this connection.`
                : "Opens View Designer. Apply first so views exist on this connection."
            }
          >
            View Designer
          </Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href={`/connections/${connectionId}/job`} data-testid="modulespec-open-job">
            Job Autopilot
          </Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href={`/connections/${connectionId}/studio`}>App Studio</Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href={projectsHref} data-testid="modulespec-open-projects">
            Projects
          </Link>
        </Button>
        {odooAppUrl && applied ? (
          <Button asChild size="sm">
            <a href={odooAppUrl} target="_blank" rel="noopener noreferrer">
              Open app in Odoo
            </a>
          </Button>
        ) : null}
      </div>
      {stockReuse ? (
        <p className="mt-3 text-xs text-muted">
          Stock reuse: Job Autopilot is the next step. This IR stays empty on purpose.
        </p>
      ) : null}
    </Card>
  );
}
