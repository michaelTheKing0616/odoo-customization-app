"use client";

import { Callout } from "@/components/ui/Callout";
import {
  glossaryLines,
  honestyLegend,
  type ProjectsHonestyGate,
} from "@/lib/projects-journey";

type ProjectHonestyBannersProps = {
  gate: ProjectsHonestyGate;
  mutateBlocked?: string | null;
  slotNote?: string | null;
};

export function ProjectHonestyBanners({
  gate,
  mutateBlocked,
  slotNote,
}: ProjectHonestyBannersProps) {
  return (
    <div className="studio-banner-stack" data-testid="projects-honesty-banners">
      <Callout variant={gate.variant} title={gate.title} testId={`projects-${gate.reason}-gate`}>
        <p data-testid="projects-gate-body">{gate.body}</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-[11px]" data-testid="projects-glossary">
          {glossaryLines().map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-[11px]" data-testid="projects-score-bars-legend">
          {honestyLegend().map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </Callout>
      {mutateBlocked ? (
        <Callout variant="warning" title="Mutations blocked" testId="projects-mutate-blocked">
          <p>{mutateBlocked}</p>
        </Callout>
      ) : null}
      {slotNote ? (
        <Callout variant="info" title="Active project slots" testId="projects-slot-note">
          <p>{slotNote}</p>
        </Callout>
      ) : null}
    </div>
  );
}
