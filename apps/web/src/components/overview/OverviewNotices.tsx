"use client";

import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import type { OverviewPageModel } from "./use-overview-page";

export function OverviewNotices({ vm }: { vm: OverviewPageModel }) {
  return (
    <>
      {vm.error ? <ErrorNotice message={vm.error} className="mt-4" /> : null}
      {vm.exportNotice ? (
        <Callout variant="info" title="Export" className="mt-4">
          {vm.exportNotice}
        </Callout>
      ) : null}
      {vm.suggestNotice ? (
        <Callout variant="info" title="Depends" className="mt-4">
          {vm.suggestNotice}
        </Callout>
      ) : null}
      {vm.jobBanner && (
        <div
          className="mt-4 flex flex-wrap items-center gap-3 border border-border-subtle bg-surface-raised/80 px-3 py-2 text-sm text-muted"
          role="status"
        >
          <span>{vm.jobBanner}</span>
          {vm.activeJobId &&
            (vm.jobStatus === "queued" || vm.jobStatus === "running") && (
              <button
                type="button"
                onClick={() => vm.onCancelJob()}
                className="border border-danger/50 px-2 py-0.5 text-xs text-danger"
              >
                Cancel
              </button>
            )}
        </div>
      )}
    </>
  );
}
