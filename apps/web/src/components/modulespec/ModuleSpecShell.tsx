"use client";

import Link from "next/link";
import { PageHeader } from "@/components/ui/layout-primitives";
import { ModuleSpecStageRail } from "./ModuleSpecStageRail";
import {
  moduleSpecHeaderDescription,
  type ModuleSpecJourneyState,
} from "@/lib/modulespec-journey";

type ModuleSpecShellProps = {
  connectionId: string;
  connectionName?: string | null;
  projectName?: string | null;
  projectId?: string | null;
  journey: ModuleSpecJourneyState;
  children: React.ReactNode;
};

export function ModuleSpecShell({
  connectionId,
  connectionName,
  projectName,
  projectId,
  journey,
  children,
}: ModuleSpecShellProps) {
  const projectsHref = projectId
    ? `/connections/${connectionId}/projects?project=${encodeURIComponent(projectId)}`
    : `/connections/${connectionId}/projects`;
  return (
    <div className="studio-refinement" data-testid="modulespec-page">
      <div className="studio-page is-canvas">
        <PageHeader
          title="ModuleSpec"
          description={moduleSpecHeaderDescription(connectionName, projectName)}
          actions={
            <>
              <Link
                href={`/connections/${connectionId}/wizard`}
                className="text-sm text-muted hover:text-ink"
              >
                Draft Studio
              </Link>
              <Link
                href={`/connections/${connectionId}/designer`}
                className="text-sm text-muted hover:text-ink"
              >
                View Designer
              </Link>
              <Link
                href={`/connections/${connectionId}/job`}
                className="text-sm text-muted hover:text-ink"
              >
                Job Autopilot
              </Link>
              <Link href={projectsHref} className="text-sm text-muted hover:text-ink">
                Projects
              </Link>
            </>
          }
        />
        <ModuleSpecStageRail journey={journey} />
        <div className="space-y-6">{children}</div>
      </div>
    </div>
  );
}
