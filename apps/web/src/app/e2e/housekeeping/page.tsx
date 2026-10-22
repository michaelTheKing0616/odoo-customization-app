"use client";

import "@/components/housekeeping/housekeeping-operate.css";

import { Suspense, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { OperateStudioBar } from "@/components/operate/OperateStudioBar";
import { Input } from "@/components/ui/Input";
import {
  Card,
  EmptyState,
  PageHeader,
} from "@/components/ui/layout-primitives";
import { formatBytes } from "@/components/housekeeping/formatBytes";
import {
  HousekeepingStepRail,
  type HousekeepingStepId,
} from "@/components/housekeeping/HousekeepingStepRail";

type HarnessState = "empty" | "scanned" | "dry-run" | "cleaned" | "confirm";

const SAMPLE_ROWS = [
  {
    id: 101,
    name: "invoice-q3.pdf",
    linked: "account.move #42",
    size: 2_400_000,
    cleanable: true,
  },
  {
    id: 102,
    name: "logo-old.png",
    linked: "res.partner #7",
    size: 890_000,
    cleanable: true,
  },
  {
    id: 103,
    name: "view-asset.css",
    linked: "standalone",
    size: 12_000,
    cleanable: false,
  },
];

function HousekeepingE2EInner() {
  const search = useSearchParams();
  const state = (search.get("state") as HarnessState) || "scanned";

  const step: HousekeepingStepId = useMemo(() => {
    if (state === "empty") return "scan";
    if (state === "dry-run") return "dry-run";
    if (state === "cleaned" || state === "confirm") return "clean";
    return "review";
  }, [state]);

  const selectedCount = state === "empty" ? 0 : state === "cleaned" ? 0 : 2;
  const showTable = state !== "empty";

  return (
    <div
      className="housekeeping-operate mx-auto max-w-5xl space-y-4 p-4 sm:p-6"
      data-testid="housekeeping-page"
    >
      <PageHeader
        title="Attachment housekeeping"
        description="Scan orphans, checksum duplicates, and large old files. Test run first. Clean is permanent and needs the confirm phrase."
      />

      <HousekeepingStepRail current={step} />

      <OperateStudioBar
        testId="housekeeping-honesty"
        tone="warning"
        title="Test run writes nothing. Clean deletes for real."
        why="Deletes are permanent in this app and may touch tier-1 parent records."
        next="Scan, select cleanable rows, test run, then Clean. Snapshot id appears on the clean result when taken first."
      />

      <div className="hk-desk housekeeping-operate" data-testid="housekeeping-desk">

      {state === "empty" ? (
        <EmptyState
          title="No scan yet"
          description="What: orphan, duplicate, or large/old attachment candidates. Why: so you can review reclaimable bytes before any delete. Next: run one of the scans below, select cleanable rows, then test run."
        />
      ) : null}

      <Card className="space-y-3 p-4" data-testid="housekeeping-orphan-card">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-ink">Orphan scan</h2>
          {showTable ? (
            <Badge variant="info" className="tabular-nums">
              2 orphan(s)
            </Badge>
          ) : null}
        </div>
        <p className="text-xs text-muted">
          Attachments whose parent record no longer exists. Standalone uploads stay
          excluded.
        </p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          data-testid="housekeeping-scan-orphans"
          disabled={state === "cleaned"}
        >
          Scan orphans
        </Button>
        {showTable ? (
          <>
            <p className="text-sm tabular-nums text-ink">
              Reclaimable: {formatBytes(3_290_000)}
            </p>
            <div className="overflow-x-auto" data-testid="housekeeping-orphan-table">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border-subtle text-muted">
                    <th className="py-2 pr-2 font-medium">Pick</th>
                    <th className="py-2 pr-2 font-medium">Name</th>
                    <th className="py-2 pr-2 font-medium">Linked</th>
                    <th className="py-2 pr-2 font-medium">Size</th>
                    <th className="py-2 pr-2 font-medium">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {SAMPLE_ROWS.map((row) => (
                    <tr key={row.id} className="border-b border-border-subtle/60">
                      <td className="py-2 pr-2 align-top">
                        <input
                          type="checkbox"
                          className="size-4"
                          disabled={!row.cleanable}
                          defaultChecked={
                            row.cleanable && state !== "cleaned"
                          }
                          readOnly
                          aria-label={`Select attachment ${row.name}`}
                        />
                      </td>
                      <td className="py-2 pr-2 align-top text-ink">{row.name}</td>
                      <td className="py-2 pr-2 align-top font-mono text-xs text-muted">
                        {row.linked}
                      </td>
                      <td className="py-2 pr-2 align-top tabular-nums">
                        {formatBytes(row.size)}
                      </td>
                      <td className="py-2 pr-2 align-top text-xs text-muted">
                        {row.cleanable ? (
                          <Badge variant="warning">cleanable</Badge>
                        ) : (
                          "excluded"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </Card>

      <Card className="space-y-3 p-4" data-testid="housekeeping-large-card">
        <h2 className="text-sm font-semibold text-ink">Large / old scan</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label="Min size (bytes)"
            type="number"
            defaultValue={1048576}
            data-testid="housekeeping-min-bytes"
            readOnly
          />
          <Input
            label="Older than (days)"
            type="number"
            defaultValue={90}
            data-testid="housekeeping-older-days"
            readOnly
          />
        </div>
        <Button type="button" variant="secondary" size="sm" disabled>
          Scan large/old
        </Button>
      </Card>

      <Card
        className="space-y-3 border-accent/20 p-4 shadow-md"
        data-testid="housekeeping-clean-card"
      >
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-ink">Clean selected</h2>
          <span data-testid="housekeeping-selected-count">
            <Badge
              variant={selectedCount ? "warning" : "default"}
              className="tabular-nums"
            >
              {selectedCount} selected
            </Badge>
          </span>
        </div>
        <p className="text-xs text-muted">
          Clean is the only teal primary on this page. Test run proves the delete
          list with no writes.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="secondary"
            disabled={selectedCount === 0}
            data-testid="housekeeping-dry-run-btn"
          >
            Test run
          </Button>
          <Button
            type="button"
            variant="primary"
            disabled={selectedCount === 0 && state !== "confirm"}
            data-testid="housekeeping-clean-btn"
          >
            Clean
          </Button>
        </div>

        {state === "dry-run" ? (
          <div
            className="space-y-2 rounded-md border border-border-subtle bg-surface px-3 py-3 text-sm"
            data-testid="housekeeping-clean-result"
            data-dry-run="true"
          >
            <p className="font-medium text-ink">Test run result (no writes)</p>
            <p className="text-muted">
              Test run: would delete 2 attachment(s) (3290000 bytes)
            </p>
            <span className="font-mono text-xs text-muted">run_id=harness-dry</span>
          </div>
        ) : null}

        {state === "cleaned" || state === "confirm" ? (
          <div
            className="space-y-2 rounded-md border border-border-subtle bg-surface px-3 py-3 text-sm"
            data-testid="housekeeping-clean-result"
            data-dry-run="false"
          >
            <p className="font-medium text-ink">Clean result (files deleted)</p>
            <p className="text-muted">
              Attachment clean (orphan): 2 ok, 0 failed of 2
            </p>
            <div className="flex flex-wrap gap-2 text-xs text-muted">
              <span className="tabular-nums">{formatBytes(3_290_000)} reclaimable</span>
              <span className="font-mono">run_id=harness-clean</span>
              <span
                className="rounded border border-accent/30 bg-accent/5 px-1.5 py-0.5 font-mono text-accent"
                data-testid="housekeeping-snapshot-id"
              >
                snapshot snap_hk_7f3a
              </span>
            </div>
          </div>
        ) : null}

        {state === "confirm" ? (
          <Callout
            variant="danger"
            title="Confirm phrase required"
            testId="housekeeping-confirm-hint"
          >
            Type &quot;I understand the risks&quot; before Clean applies. Snapshot
            id appears on the result when taken first.
          </Callout>
        ) : null}
      </Card>
      </div>
    </div>
  );
}

export default function HousekeepingE2EPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading...</main>}>
      <HousekeepingE2EInner />
    </Suspense>
  );
}
