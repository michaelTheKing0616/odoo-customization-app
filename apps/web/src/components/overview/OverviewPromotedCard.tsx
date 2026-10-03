"use client";

import { Button } from "@/components/ui/Button";
import { Card, EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import type { OverviewPageModel } from "./use-overview-page";

export function OverviewPromotedCard({ vm }: { vm: OverviewPageModel }) {
  return (
    <Card className="mt-6 p-5">
      <h2 className="text-xl font-semibold text-ink">Promoted modules</h2>
      <p className="mt-1 text-sm text-muted">
        History of modules installed via promote. Uninstall requires confirmation.
      </p>
      {vm.loading ? (
        <div className="mt-4 space-y-2" data-testid="overview-promoted-loading">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : vm.promoted.length === 0 ? (
        <div className="mt-4" data-testid="overview-promoted-empty">
          <EmptyState
            title="No promoted modules yet"
            description="Export and promote a sandbox-validated zip above to record install history on this connection."
            action={
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  document
                    .getElementById("overview-export-card")
                    ?.scrollIntoView({ behavior: "smooth" });
                }}
              >
                Open export panel
              </Button>
            }
          />
        </div>
      ) : (
        <ul className="mt-4 space-y-2 text-sm">
          {vm.promoted.map((p) => (
            <li
              key={p.id}
              className="flex flex-wrap items-center justify-between gap-2 border border-border-subtle px-3 py-2"
            >
              <span>
                <span className="font-mono text-muted">{p.module_name}</span>{" "}
                <span className="text-muted">
                  · {p.method} · {p.status}
                </span>
              </span>
              {p.status === "installed" && (
                <button
                  type="button"
                  disabled={vm.exportBusy}
                  onClick={() => {
                    vm.setUninstallTarget(p.module_name);
                    vm.setUninstallPhrase("");
                  }}
                  className="border border-danger/50 px-2 py-1 text-xs text-danger disabled:opacity-40"
                >
                  Uninstall
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {vm.uninstallTarget && (
        <div className="mt-4 border border-warning/40 bg-warning-subtle p-4">
          <p className="text-sm text-warning-strong">
            Uninstall <code className="font-mono">{vm.uninstallTarget}</code>?
          </p>
          <label className="mt-3 block text-sm">
            <span className="text-muted">
              Type <code className="text-warning-strong">I understand the risks</code>
            </span>
            <input
              value={vm.uninstallPhrase}
              onChange={(e) => vm.setUninstallPhrase(e.target.value)}
              className="mt-1 w-full max-w-md border border-warning/40 bg-surface px-3 py-2 text-sm"
            />
          </label>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled={vm.exportBusy}
              onClick={vm.onUninstall}
              className="h-9 bg-danger px-4 text-sm font-semibold text-white disabled:opacity-60"
            >
              Uninstall
            </button>
            <button
              type="button"
              onClick={() => vm.setUninstallTarget(null)}
              className="h-9 border border-warning/40 px-4 text-sm text-warning"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
