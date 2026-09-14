"use client";

import Link from "next/link";
import { PageHeader } from "@/components/ui/layout-primitives";
import { ProjectStageRail } from "./ProjectStageRail";
import {
  projectsHeaderDescription,
  type ProjectsJourneyState,
} from "@/lib/projects-journey";

type ProjectShellProps = {
  connectionId: string;
  connectionName?: string | null;
  projectName?: string | null;
  journey: ProjectsJourneyState;
  children: React.ReactNode;
};

export function ProjectShell({
  connectionId,
  connectionName,
  projectName,
  journey,
  children,
}: ProjectShellProps) {
  return (
    <div className="studio-refinement" data-testid="projects-page">
      <div className="studio-page is-canvas">
        <PageHeader
          title="Projects"
          description={projectsHeaderDescription(connectionName, projectName)}
          actions={
            <>
              <Link
                href={`/connections/${connectionId}/modulespec`}
                className="text-sm text-muted hover:text-ink"
              >
                ModuleSpec
              </Link>
              <Link
                href={`/connections/${connectionId}/designer`}
                className="text-sm text-muted hover:text-ink"
              >
                View Designer
              </Link>
              <Link
                href={`/connections/${connectionId}/journal`}
                className="text-sm text-muted hover:text-ink"
              >
                Snapshots
              </Link>
            </>
          }
        />
        <ProjectStageRail journey={journey} />
        <div className="space-y-6">{children}</div>
      </div>
    </div>
  );
}
