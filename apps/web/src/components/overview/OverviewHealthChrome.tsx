"use client";

import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { HealthCheckBanner } from "@/components/HealthCheckBanner";
import { CapabilitiesPostcard } from "@/components/shell/CapabilitiesPostcard";
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

      {vm.connection ? (
        <CapabilitiesPostcard
          connection={vm.connection}
          capabilities={vm.connection.capabilities}
          probing={vm.probing}
          onReprobe={vm.onReprobe}
        />
      ) : null}

      {vm.connection && (
        <CapabilityProbePanel
          capabilities={vm.connection.capabilities}
          className="mt-3"
          refreshing={vm.probing}
          onRefresh={vm.onReprobe}
        />
      )}
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
