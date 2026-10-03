"use client";

import Link from "next/link";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { automationsHref } from "@/lib/automationForm";
import { api } from "@/lib/api";
import type { DesignerPageModel } from "@/components/designer/useDesignerPageModel";

export function DesignerPageNotices({ m }: { m: DesignerPageModel }) {
  return (
    <>
      {m.connection ? <FirstWriteInterstitial connection={m.connection} /> : null}
      <p className="mt-2 text-sm text-muted">
        Removing a field from the view does not delete the database column.{" "}
        <Link
          href={automationsHref(m.connectionId, m.model)}
          className="text-accent hover:underline"
          data-testid="designer-automations-link"
        >
          Open automations for this model
        </Link>
        .
      </p>
      <VersionAwarenessBanner capabilities={m.connection?.capabilities} />
      <CapabilityProbePanel
        capabilities={m.connection?.capabilities}
        defaultOpen={false}
        className="mt-2"
        refreshing={m.probing}
        onRefresh={() => {
          void (async () => {
            m.setProbing(true);
            m.setError(null);
            try {
              const result = await api.probeConnection(m.connectionId);
              m.setConnection((prev) =>
                prev
                  ? {
                      ...prev,
                      server_version: result.server_version,
                      capabilities: result.capabilities,
                    }
                  : prev,
              );
            } catch (err) {
              m.setError(err instanceof Error ? err.message : "Probe failed");
            } finally {
              m.setProbing(false);
            }
          })();
        }}
      />
      {m.error ? <ErrorNotice message={m.error} className="mt-2" /> : null}
      {m.notice ? (
        <Callout variant="info" title="Notice" className="mt-2">
          {m.notice}
        </Callout>
      ) : null}
    </>
  );
}
