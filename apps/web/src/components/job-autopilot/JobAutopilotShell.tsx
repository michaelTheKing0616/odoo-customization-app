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
            <>
              <Link
                href={`/connections/${connectionId}/wizard`}
                className="text-sm text-muted hover:text-ink"
              >
                Draft Studio
              </Link>
              <Link
                href={`/connections/${connectionId}/studio`}
                className="text-sm text-muted hover:text-ink"
              >
                App Studio
              </Link>
            </>
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
