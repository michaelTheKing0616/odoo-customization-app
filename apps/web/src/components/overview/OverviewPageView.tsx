"use client";

import { useEffect, useState } from "react";
import type { LiveSnapshot } from "@/lib/api";
import { CapabilityExtras } from "./CapabilityExtras";
import { PageHeader } from "@/components/ui/layout-primitives";
import { Tabs } from "@/components/ui/Tabs";
import { OverviewExportCard } from "./OverviewExportCard";
import { OverviewHealthChrome } from "./OverviewHealthChrome";
import { OverviewActions, OverviewHomeChrome } from "./OverviewHomeChrome";
import { LiveDatabaseSection } from "./live/LiveDatabaseSection";
import { OverviewNotices } from "./OverviewNotices";
import { OverviewPlaybooksTab } from "./OverviewPlaybooksTab";
import { OverviewPromotedCard } from "./OverviewPromotedCard";
import type { OverviewPageModel } from "./use-overview-page";
import type { OverviewSection } from "./use-overview-page-state";

export function OverviewPageView(vm: OverviewPageModel) {
  const [live, setLive] = useState<LiveSnapshot | null>(null);
  const hasLibrary = !!live?.models.some((m) => m.model === "x_lib_book");
  const { loadLibraryStats } = vm;
  useEffect(() => {
    if (hasLibrary) void loadLibraryStats();
  }, [hasLibrary, loadLibraryStats]);
  return (
    <div className="mx-auto max-w-6xl" data-testid="connection-overview">
      <PageHeader
        title="Overview"
        description="How your Odoo database is doing, and what needs you."
        actions={<OverviewActions connectionId={vm.connectionId} />}
      />
      <LiveDatabaseSection
        connectionId={vm.connectionId}
        onSnapshot={setLive}
        capabilityExtras={<CapabilityExtras vm={vm} />}
      />
      <OverviewHealthChrome vm={vm} />
      <OverviewHomeChrome vm={vm} modelCount={live ? live.counts.models : null} />

      <Tabs
        className="mt-8"
        value={vm.section === "models" ? "home" : vm.section}
        onValueChange={(v) => vm.setSection(v as OverviewSection)}
        items={[
          {
            value: "home",
            label: "Playbooks",
            content: <OverviewPlaybooksTab vm={vm} />,
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
