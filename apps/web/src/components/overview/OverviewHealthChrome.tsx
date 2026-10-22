"use client";

import { HealthCheckBanner } from "@/components/HealthCheckBanner";
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";
import { ProductionReadinessPanel } from "@/components/shell/ProductionReadinessPanel";
import { WriteModeUnlockPanel } from "@/components/shell/WriteModeUnlockPanel";
import type { OverviewPageModel } from "./use-overview-page";

export function OverviewHealthChrome({ vm }: { vm: OverviewPageModel }) {
  return (
    <>
      {vm.connection ? (
        <WriteModeUnlockPanel
          connection={vm.connection}
          onUpdated={(updated) => vm.setConnection(updated)}
        />
      ) : null}

      {vm.connection ? (
        <ProductionReadinessPanel
          connection={vm.connection}
          onRefreshConnection={vm.onRefreshReadiness}
        />
      ) : null}

      <FirstWriteInterstitial connection={vm.connection} />

      {vm.connection && (
        <HealthCheckBanner
          connectionId={vm.connectionId}
          connection={vm.connection}
          onRefreshConnection={vm.onRefreshHealth}
        />
      )}
    </>
  );
}
