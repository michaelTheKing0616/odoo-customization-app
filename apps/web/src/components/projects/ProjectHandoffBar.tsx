"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { designerHref, journalHref, modulespecHref } from "@/lib/projects-journey";

type ProjectHandoffBarProps = {
  connectionId: string;
  projectId?: string | null;
  designerModel?: string | null;
};

export function ProjectHandoffBar({
  connectionId,
  projectId,
  designerModel,
}: ProjectHandoffBarProps) {
  return (
    <Card className="p-5" data-testid="projects-handoff-bar">
      <h2 className="text-lg font-semibold text-ink">Open related surfaces</h2>
      <p className="mt-1 text-sm text-muted">
        Projects is versioned draft history. ModuleSpec is the IR. View Designer edits live forms.
        Snapshots live in the change journal. Promote stays human.
      </p>
      <div className="job-handoff-bar mt-4">
        {projectId ? (
          <Button asChild variant="ghost" size="sm">
            <Link href={modulespecHref(connectionId, projectId)} data-testid="projects-handoff-modulespec">
              ModuleSpec
            </Link>
          </Button>
        ) : (
          <Button asChild variant="ghost" size="sm">
            <Link href={`/connections/${connectionId}/modulespec`}>ModuleSpec</Link>
          </Button>
        )}
        <Button asChild variant="ghost" size="sm">
          <Link href={designerHref(connectionId, designerModel)} data-testid="projects-handoff-designer">
            View Designer
          </Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href={journalHref(connectionId)} data-testid="projects-handoff-journal">
            Snapshots
          </Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href={`/connections/${connectionId}/wizard`}>Draft Studio</Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href={`/connections/${connectionId}/job`}>Job Autopilot</Link>
        </Button>
      </div>
    </Card>
  );
}
