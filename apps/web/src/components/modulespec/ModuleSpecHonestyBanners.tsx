"use client";

import { Callout } from "@/components/ui/Callout";
import { honestyLegend } from "@/lib/modulespec-journey";

type ModuleSpecHonestyBannersProps = {
  applyBlocked?: string | null;
  saveBlocked?: string | null;
  stockReuse?: boolean;
  completenessNote?: string | null;
};

export function ModuleSpecHonestyBanners({
  applyBlocked,
  saveBlocked,
  stockReuse,
  completenessNote,
}: ModuleSpecHonestyBannersProps) {
  const blocked = applyBlocked ?? saveBlocked;
  return (
    <div className="studio-banner-stack" data-testid="modulespec-honesty-banners">
      {stockReuse ? (
        <Callout variant="info" title="Stock reuse — no custom ModuleSpec" testId="modulespec-stock-reuse">
          <p>
            Empty models is the correct IR when stock Community apps already cover the brief.
            Open Job Autopilot for sandbox install and RPC smoke. Do not Generate UI.
          </p>
        </Callout>
      ) : null}
      {blocked ? (
        <Callout variant="warning" title="Blocked" testId="modulespec-blocked">
          <p>{blocked}</p>
        </Callout>
      ) : null}
      <Callout variant="info" title="Three independent bars" testId="modulespec-score-bars">
        {completenessNote ? (
          <p className="mb-2" data-testid="modulespec-completeness-note">
            {completenessNote}
          </p>
        ) : null}
        <ul className="list-disc space-y-1 pl-5 text-[11px]" data-testid="modulespec-score-bars-legend">
          {honestyLegend().map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </Callout>
    </div>
  );
}
