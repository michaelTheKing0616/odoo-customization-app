"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, AuditLogRow, Connection, HealthCheckRun, SnapshotRow } from "@/lib/api";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { HealthCheckBanner } from "@/components/HealthCheckBanner";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Card, PageHeader } from "@/components/ui/layout-primitives";

type TimelineFilter = "all" | "snapshot" | "audit" | "health";

type TimelineEntry =
  | { kind: "snapshot"; at: string; snapshot: SnapshotRow }
  | { kind: "audit"; at: string; audit: AuditLogRow }
  | { kind: "health"; at: string; run: HealthCheckRun };

function reversibilityBadge(reversible: string) {
  if (reversible === "yes") return <Badge variant="success">Rollback yes</Badge>;
  if (reversible === "partial")
    return <Badge variant="warning">Rollback partial</Badge>;
  return <Badge variant="danger">Rollback no</Badge>;
}

function reversibilityNote(reversible: string): string {
  if (reversible === "yes") return "Snapshot can restore this metadata definition.";
  if (reversible === "partial")
    return "Partial restore — some fields or side effects may remain.";
  return "Not reversible — undo is disabled for this snapshot.";
}

export default function ChangeJournalPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [audits, setAudits] = useState<AuditLogRow[]>([]);
  const [healthRuns, setHealthRuns] = useState<HealthCheckRun[]>([]);
  const [filter, setFilter] = useState<TimelineFilter>("all");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [conn, snaps, logs, runs] = await Promise.all([
      api.getConnection(connectionId),
      api.listSnapshots(connectionId),
      api.listAuditLogs(80).catch(() => [] as AuditLogRow[]),
      api.listHealthCheckRuns(connectionId, 10).catch(() => [] as HealthCheckRun[]),
    ]);
    setConnection(conn);
    setSnapshots(snaps);
    setHealthRuns(runs);
    setAudits(
      logs.filter(
        (l) =>
          l.path.includes(connectionId) ||
          l.path.includes("/snapshots") ||
          l.path.includes("/power-ops") ||
          l.path.includes("/data-import") ||
          l.path.includes("/automations") ||
          l.path.includes("/access") ||
          l.path.includes("/config"),
      ),
    );
  }, [connectionId]);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  const timeline = useMemo(() => {
    const entries: TimelineEntry[] = [];
    for (const s of snapshots) {
      entries.push({
        kind: "snapshot",
        at: s.created_at ?? "",
        snapshot: s,
      });
    }
    for (const a of audits) {
      entries.push({
        kind: "audit",
        at: a.created_at ?? "",
        audit: a,
      });
    }
    for (const h of healthRuns) {
      entries.push({
        kind: "health",
        at: h.finished_at ?? h.created_at ?? "",
        run: h,
      });
    }
    entries.sort((a, b) => (b.at || "").localeCompare(a.at || ""));
    if (filter === "all") return entries;
    if (filter === "snapshot") return entries.filter((e) => e.kind === "snapshot");
    if (filter === "audit") return entries.filter((e) => e.kind === "audit");
    return entries.filter((e) => e.kind === "health");
  }, [snapshots, audits, healthRuns, filter]);

  async function undo(snapshotId: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api.rollbackSnapshot(connectionId, snapshotId);
      setNotice(`Restored ${res.restored} #${res.id}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setBusy(false);
    }
  }

  const filters: { id: TimelineFilter; label: string }[] = [
    { id: "all", label: "All" },
    { id: "snapshot", label: "Snapshots" },
    { id: "audit", label: "Audit" },
    { id: "health", label: "Health" },
  ];

  return (
    <div className="mx-auto max-w-5xl" data-testid="journal-page">
      <PageHeader
        title="Change journal"
        description="Metadata snapshots with rollback · API audit · post-upgrade health checks"
      />
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
      <HealthCheckBanner
        connectionId={connectionId}
        connection={connection}
        onRefreshConnection={refresh}
      />

      {error ? <ErrorNotice message={error} className="mt-4" /> : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

      <div className="mt-6 flex flex-wrap gap-2">
        {filters.map((f) => (
          <Button
            key={f.id}
            type="button"
            variant={filter === f.id ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setFilter(f.id)}
          >
            {f.label}
          </Button>
        ))}
      </div>

      <ul className="relative mt-8 space-y-4 border-l border-border-subtle pl-6">
        {timeline.map((entry) => {
          if (entry.kind === "snapshot") {
            const s = entry.snapshot;
            return (
              <li key={`snap-${s.id}`} className="relative">
                <span className="absolute -left-[1.6rem] top-2 h-2.5 w-2.5 rounded-full bg-accent" />
                <Card className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="info">Snapshot</Badge>
                        {reversibilityBadge(s.reversible)}
                      </div>
                      <p className="mt-2 font-medium text-ink">{s.label}</p>
                      <p className="mt-1 font-mono text-xs text-muted">
                        {s.resource_type} · {s.resource_key}
                        {s.created_at ? ` · ${s.created_at}` : ""}
                      </p>
                      <p className="mt-2 text-xs text-muted">
                        {reversibilityNote(s.reversible)}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={busy || s.reversible === "none" || s.reversible === "no"}
                      onClick={() => void undo(s.id)}
                    >
                      Rollback
                    </Button>
                  </div>
                </Card>
              </li>
            );
          }
          if (entry.kind === "audit") {
            const a = entry.audit;
            return (
              <li key={`audit-${a.id}`} className="relative">
                <span className="absolute -left-[1.6rem] top-2 h-2.5 w-2.5 rounded-full bg-muted" />
                <Card className="p-4 font-mono text-xs">
                  <Badge variant="default">Audit</Badge>
                  <p className="mt-2 text-ink">
                    <span className="text-accent">{a.method}</span> {a.path} ·{" "}
                    {a.status_code}
                    {a.duration_ms != null ? ` · ${a.duration_ms}ms` : ""}
                    {a.created_at ? ` · ${a.created_at}` : ""}
                  </p>
                </Card>
              </li>
            );
          }
          const run = entry.run;
          return (
            <li key={`health-${run.id}`} className="relative">
              <span className="absolute -left-[1.6rem] top-2 h-2.5 w-2.5 rounded-full bg-warning" />
              <Card className="p-4 text-sm">
                <Badge variant={run.broken_count > 0 ? "danger" : "success"}>
                  Health · {run.status}
                </Badge>
                <p className="mt-2 font-medium text-ink">
                  {run.trigger === "auto" ? "Auto sweep" : "Manual sweep"}
                  {run.broken_count > 0 ? (
                    <span className="text-danger"> · {run.broken_count} broken</span>
                  ) : run.status === "complete" ? (
                    <span className="text-muted"> · {run.ok_count} OK</span>
                  ) : null}
                </p>
                <p className="mt-1 text-xs text-muted">
                  {run.previous_version && run.current_version
                    ? `${run.previous_version} → ${run.current_version} · `
                    : ""}
                  {run.message}
                  {run.finished_at ? ` · ${run.finished_at}` : ""}
                </p>
                {run.items.filter((i) => i.status === "broken").length > 0 ? (
                  <ul className="mt-2 space-y-1 text-xs">
                    {run.items
                      .filter((i) => i.status === "broken")
                      .map((item) => (
                        <li key={item.artifact_id}>
                          <Link href={item.deep_link} className="text-accent hover:underline">
                            {item.label}
                          </Link>
                          <span className="text-muted"> — {item.reason}</span>
                        </li>
                      ))}
                  </ul>
                ) : null}
              </Card>
            </li>
          );
        })}
        {timeline.length === 0 ? (
          <li className="text-sm text-muted">
            No entries for this filter. Destructive edits create snapshots automatically.
          </li>
        ) : null}
      </ul>
    </div>
  );
}
