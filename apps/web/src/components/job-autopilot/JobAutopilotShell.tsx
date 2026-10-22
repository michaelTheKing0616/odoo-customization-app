"use client";

import Link from "next/link";
import { PageHeader } from "@/components/ui/layout-primitives";
import { JobAutopilotStageRail } from "./JobAutopilotStageRail";
import {
  jobAutopilotHeaderDescription,
  type JobAutopilotJourneyState,
} from "@/lib/job-autopilot-journey";
import { BuildSpineBar } from "@/components/build/BuildSpineBar";
import { useBuildSpineHandoff } from "@/lib/use-build-spine-handoff";

type JobAutopilotShellProps = {
  connectionId: string;
  connectionName?: string;
  writeMode?: string | null;
  journey: JobAutopilotJourneyState;
  children: React.ReactNode;
};

export function JobAutopilotShell({
  connectionId,
  connectionName,
  writeMode,
  journey,
  children,
}: JobAutopilotShellProps) {
  const handoff = useBuildSpineHandoff(connectionId);
  return (
    <div className="studio-refinement" data-testid="job-autopilot">
      <div className="studio-page">
        <PageHeader
          title="Job Autopilot"
          description={jobAutopilotHeaderDescription(connectionName, writeMode)}
          actions={
            <nav className="job-cluster-nav" aria-label="Studio cluster">
              <Link
                href={`/connections/${connectionId}/studio`}
                className="job-cluster-link"
              >
                App Studio
              </Link>
              <Link
                href={`/connections/${connectionId}/wizard`}
                className="job-cluster-link"
              >
                Draft Studio
              </Link>
              <span className="job-cluster-link is-current" aria-current="page">
                Job Autopilot
              </span>
            </nav>
          }
        />
        <JobAutopilotStageRail journey={journey} />
        <div className="mb-4">
          <BuildSpineBar
            connectionId={connectionId}
            activeMode="stock_autopilot"
            handoff={handoff}
            compact
          />
        </div>
        <div className="space-y-6">{children}</div>
      </div>
    </div>
  );
}
