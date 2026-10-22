"use client";

import { Callout } from "@/components/ui/Callout";
import { SCORE_BARS } from "@/lib/copy-guide";
import {
  jobAutopilotOnlineHonesty,
  type JobAutopilotGate,
} from "@/lib/job-autopilot-journey";

type JobAutopilotHonestyBannersProps = {
  gate: JobAutopilotGate;
  showOverviewNote?: boolean;
  contractNote?: string | null;
  /** Odoo Online: never imply live Python module install. */
  isOdooOnline?: boolean;
};

export function JobAutopilotHonestyBanners({
  gate,
  showOverviewNote,
  contractNote,
  isOdooOnline,
}: JobAutopilotHonestyBannersProps) {
  const online = isOdooOnline ? jobAutopilotOnlineHonesty() : null;
  return (
    <div className="studio-banner-stack">
      <Callout
        variant={gate.variant}
        title={gate.title}
        testId={`job-autopilot-${gate.reason}-gate`}
      >
        <p data-testid="job-autopilot-gate-body">{gate.body}</p>
        {gate.reason === "production" ? (
          <p className="mt-2 text-sm" data-testid="job-autopilot-production-refuse">
            Run Autopilot stays disabled on this connection. Completeness 10.0 is not a
            production write.
          </p>
        ) : null}
        <ul className="mt-2 list-disc space-y-1 pl-5 text-[11px]" data-testid="job-score-bars-legend">
          <li>{SCORE_BARS.completeness}</li>
          <li>{SCORE_BARS.certification}</li>
          <li>{SCORE_BARS.autopilot}</li>
        </ul>
        {contractNote ? (
          <p className="mt-2 text-xs" data-testid="job-autopilot-contract-note">
            {contractNote}
          </p>
        ) : null}
      </Callout>
      {online ? (
        <Callout variant="warning" title={online.title} testId="job-autopilot-online-honesty">
          <p className="text-sm" data-testid="job-autopilot-online-body">
            {online.body}
          </p>
        </Callout>
      ) : null}
      {showOverviewNote ? (
        <Callout variant="info" title="Overview checklist is not this job">
          <p className="text-sm">
            The Overview production-readiness panel gates production write mode only. It
            does not score or block sandbox Autopilot. Amber bootstrap warnings on this
            page are the job signal.
          </p>
        </Callout>
      ) : null}
    </div>
  );
}
