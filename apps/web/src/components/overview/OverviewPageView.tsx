"use client";

import { PageHeader } from "@/components/ui/layout-primitives";
import { Tabs } from "@/components/ui/Tabs";
import { OverviewExportCard } from "./OverviewExportCard";
import { OverviewHealthChrome } from "./OverviewHealthChrome";
import { OverviewHomeChrome } from "./OverviewHomeChrome";
import { OverviewModelsSection } from "./OverviewModelsSection";
import { OverviewNotices } from "./OverviewNotices";
import { OverviewPlaybooksTab } from "./OverviewPlaybooksTab";
import { OverviewPromotedCard } from "./OverviewPromotedCard";
import type { OverviewPageModel } from "./use-overview-page";
import type { OverviewSection } from "./use-overview-page-state";

export function OverviewPageView(vm: OverviewPageModel) {
  return (
    <div className="mx-auto max-w-6xl" data-testid="connection-overview">
      <PageHeader
        title="Overview"
        description="Your connection at a glance — health, models, and export paths."
      />
      <OverviewHealthChrome vm={vm} />
      <OverviewHomeChrome vm={vm} />

      <Tabs
        className="mt-8"
        value={vm.section}
        onValueChange={(v) => vm.setSection(v as OverviewSection)}
        items={[
          {
            value: "home",
            label: "Overview",
            content: <OverviewPlaybooksTab vm={vm} />,
          },
          {
            value: "models",
            label: "Models",
            content: <OverviewModelsSection vm={vm} />,
          },
          {
            value: "develop",
            label: "Develop",
            content: (
              <p className="text-sm text-muted">
                Export, sandbox, promote, and promoted-module history appear below when this tab is selected.
              </p>
            ),
          },
        ]}
      />

      <OverviewNotices vm={vm} />
      {vm.section === "develop" ? (
        <>
          <OverviewExportCard vm={vm} />
          <OverviewPromotedCard vm={vm} />
        </>
      ) : null}
    </div>
  );
}
