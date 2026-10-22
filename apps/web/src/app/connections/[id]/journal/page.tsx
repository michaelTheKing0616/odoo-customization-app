"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, AuditLogRow, Connection, HealthCheckRun, SnapshotRow } from "@/lib/api";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Skeleton } from "@/components/ui/layout-primitives";
import { PageHeader } from "@/components/ui/layout-primitives";
import { JournalBatchPanel } from "@/components/batch-os/JournalBatchPanel";
import { DocumentBatchPanel } from "@/components/batch-os/DocumentBatchPanel";
import { MasterDataBatchPanel } from "@/components/batch-os/MasterDataBatchPanel";
import { OrderBatchPanel } from "@/components/batch-os/OrderBatchPanel";
import { JournalErrorNotice } from "@/components/journal/JournalErrorNotice";
import { JournalStageRail } from "@/components/journal/JournalStageRail";
import { HistoryTimeline } from "@/components/history/HistoryTimeline";
import { JournalStateGuide } from "@/components/journal/JournalStateGuide";
import {
  CHAIN_VERIFY_NOTE,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  REFRESH_CTA,
  auditReplayGuide,
  canRollback,
  emptyJournalGuide,
  healthSweepGuide,
  idleJournalGuide,
  irreversibleGuide,
  journalHonestyGuide,
  journalStepFromState,
  partialRollbackGuide,
  reversibilityCopy,
  rollbackSuccessGuide,
  sanitizeJournalCopy,
  type JournalErrorContext,
  type JournalTab,
  type JournalTimelineFilter,
} from "@/lib/journalScreen";
import "@/components/journal/journal-operate.css";

type TimelineEntry =
  | { kind: "snapshot"; at: string; snapshot: SnapshotRow }
  | { kind: "audit"; at: string; audit: AuditLogRow }
  | { kind: "health"; at: string; run: HealthCheckRun };

function reversibilityBadge(reversible: string) {
  if (reversible === "yes") return <Badge variant="success">Fully reversible</Badge>;
  if (reversible === "partial")
    return <Badge variant="warning">Partially reversible</Badge>;
  return <Badge variant="danger">Not reversible</Badge>;
}

function entryKey(entry: TimelineEntry): string {
  if (entry.kind === "snapshot") return `snap-${entry.snapshot.id}`;
  if (entry.kind === "audit") return `audit-${entry.audit.id}`;
  return `health-${entry.run.id}`;
}

export default function ChangeJournalPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [audits, setAudits] = useState<AuditLogRow[]>([]);
  const [healthRuns, setHealthRuns] = useState<HealthCheckRun[]>([]);
  const [filter, setFilter] = useState<JournalTimelineFilter>("all");
  const [error, setError] = useState<string | null>(null);
  const [errorContext, setErrorContext] = useState<JournalErrorContext>("load");
  const [notice, setNotice] = useState<string | null>(null);
  const [restoredLabel, setRestoredLabel] = useState<string | null>(null);
  const [restoredId, setRestoredId] = useState<string | number | null>(null);
  const [busy, setBusy] = useState(false);
  const searchParams = useSearchParams();
  // Find anything (Cmd-K) links straight to a change: ?change=<snapshot id>.
  const [selectedKey, setSelectedKey] = useState<string | null>(() => {
    const change = searchParams.get("change");
    return change ? `snap-${change}` : null;
  });
  const initialTab = (searchParams.get("tab") as JournalTab | null) || "timeline";
  const [tab, setTab] = useState<JournalTab>(
    initialTab === "batch" ||
      initialTab === "invoices" ||
      initialTab === "orders" ||
      initialTab === "master"
      ? initialTab
      : "timeline",
  );
  const [listHydrated, setListHydrated] = useState(false);

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
          l.path.includes("/code-studio") ||
          l.path.includes("/access") ||
          l.path.includes("/config"),
      ),
    );
  }, [connectionId]);

  useEffect(() => {
    setListHydrated(false);
    setError(null);
    setErrorContext("load");
    refresh()
      .catch((err: Error) => {
        setErrorContext("load");
        setError(err.message);
      })
      .finally(() => setListHydrated(true));
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

  const selectedEntry = useMemo(
    () => timeline.find((e) => entryKey(e) === selectedKey) ?? null,
    [timeline, selectedKey],
  );

  const stageStep = journalStepFromState({
    entryCount: timeline.length,
    hasSelection: Boolean(selectedEntry),
    rollbackDone: Boolean(restoredLabel),
    tab,
  });

  async function undo(snapshot: SnapshotRow) {
    setBusy(true);
    setError(null);
    setNotice(null);
    setRestoredLabel(null);
    setRestoredId(null);
    setErrorContext("rollback");
    try {
      const res = await api.rollbackSnapshot(connectionId, snapshot.id);
      setRestoredLabel(snapshot.label);
      setRestoredId(res.id);
      setNotice(`Restored ${res.restored} #${res.id}`);
      await refresh();
    } catch (err) {
      setErrorContext("rollback");
      setError(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setBusy(false);
    }
  }

  function refreshTimeline() {
    setListHydrated(false);
    setError(null);
    setErrorContext("refresh");
    void refresh()
      .catch((err: Error) => {
        setErrorContext("refresh");
        setError(err.message);
      })
      .finally(() => setListHydrated(true));
  }

  const filters: { id: JournalTimelineFilter; label: string }[] = [
    { id: "all", label: "All" },
    { id: "snapshot", label: "Snapshots" },
    { id: "audit", label: "Audit" },
    { id: "health", label: "Health" },
  ];

  const tabs: { id: JournalTab; label: string; testId?: string }[] = [
    { id: "timeline", label: "Timeline" },
    { id: "batch", label: "Batch flow" },
    { id: "invoices", label: "Invoices & bills", testId: "journal-tab-invoices" },
    { id: "orders", label: "Orders", testId: "journal-tab-orders" },
    { id: "master", label: "Master data", testId: "journal-tab-master" },
  ];

  return (
    <div className="journal-operate" data-testid="journal-page">
      <PageHeader title={PAGE_TITLE} description={PAGE_DESCRIPTION} />
      <VersionAwarenessBanner capabilities={connection?.capabilities} />

      {tab === "timeline" ? <JournalStageRail step={stageStep} /> : null}
      {tab === "timeline" && connectionId ? <HistoryTimeline connectionId={connectionId} /> : null}

      <div className="jn-tabs" data-testid="journal-tabs" role="tablist" aria-label="Journal surfaces">
        {tabs.map((t) => (
          <Button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className="jn-tab"
            data-active={tab === t.id ? "true" : "false"}
            variant={tab === t.id ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setTab(t.id)}
            data-testid={t.testId}
          >
            {t.label}
          </Button>
        ))}
      </div>

      {tab === "batch" ? (
        <div className="mt-6">
          <JournalBatchPanel connectionId={connectionId} />
        </div>
      ) : tab === "invoices" ? (
        <div className="mt-6">
          <DocumentBatchPanel connectionId={connectionId} />
        </div>
      ) : tab === "orders" ? (
        <div className="mt-6">
          <OrderBatchPanel connectionId={connectionId} />
        </div>
      ) : tab === "master" ? (
        <div className="mt-6">
          <MasterDataBatchPanel connectionId={connectionId} />
        </div>
      ) : (
        <>
          <JournalStateGuide
            tone="warning"
            testId="journal-honesty"
            guide={journalHonestyGuide()}
          />

          <p className="jn-chain-note" data-testid="journal-chain-note">
            {CHAIN_VERIFY_NOTE}
          </p>

          {error ? (
            <JournalErrorNotice
              className="mt-4"
              message={error}
              context={errorContext}
              onDismiss={() => setError(null)}
              onRetry={
                errorContext === "rollback" && selectedEntry?.kind === "snapshot"
                  ? () => void undo(selectedEntry.snapshot)
                  : refreshTimeline
              }
            />
          ) : null}

          {restoredLabel ? (
            <JournalStateGuide
              className="mt-4"
              tone="success"
              live
              testId="journal-rollback-success"
              guide={rollbackSuccessGuide(restoredLabel, restoredId ?? undefined)}
            />
          ) : null}

          {notice && !restoredLabel ? (
            <Callout variant="info" title="Notice" className="mt-4">
              {sanitizeJournalCopy(notice)}
            </Callout>
          ) : null}

          {!listHydrated ? null : timeline.length === 0 && !error ? (
            <JournalStateGuide
              tone="accent"
              testId="journal-empty-guide"
              guide={emptyJournalGuide()}
              actions={
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={refreshTimeline}
                >
                  {REFRESH_CTA}
                </Button>
              }
            />
          ) : timeline.length > 0 && !selectedEntry && !restoredLabel ? (
            <JournalStateGuide
              tone="neutral"
              testId="journal-idle-guide"
              guide={idleJournalGuide()}
            />
          ) : null}

          {selectedEntry?.kind === "snapshot" ? (
            canRollback(selectedEntry.snapshot.reversible) ? (
              selectedEntry.snapshot.reversible === "partial" ? (
                <JournalStateGuide
                  tone="warning"
                  testId="journal-partial-guide"
                  guide={partialRollbackGuide()}
                />
              ) : null
            ) : (
              <JournalStateGuide
                tone="danger"
                testId="journal-irreversible-guide"
                guide={irreversibleGuide()}
              />
            )
          ) : null}

          {selectedEntry?.kind === "audit" ? (
            <JournalStateGuide
              tone="neutral"
              testId="journal-audit-guide"
              guide={auditReplayGuide()}
            />
          ) : null}

          {selectedEntry?.kind === "health" ? (
            <JournalStateGuide
              tone={selectedEntry.run.broken_count > 0 ? "warning" : "success"}
              testId="journal-health-guide"
              guide={healthSweepGuide(selectedEntry.run.broken_count)}
            />
          ) : null}

          <div className="jn-filters" data-testid="journal-filters">
            {filters.map((f) => (
              <Button
                key={f.id}
                type="button"
                className="jn-filter"
                data-active={filter === f.id ? "true" : "false"}
                variant={filter === f.id ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setFilter(f.id)}
              >
                {f.label}
              </Button>
            ))}
          </div>

          {busy ? (
            <div className="jn-progress" aria-busy="true" data-testid="journal-busy">
              Restoring snapshot…
            </div>
          ) : null}

          {!listHydrated ? (
            <div className="mt-8 space-y-4" data-testid="journal-timeline-loading">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : (
            <ul className="jn-timeline" data-testid="journal-timeline">
              {timeline.map((entry) => {
                const key = entryKey(entry);
                const selected = selectedKey === key;
                if (entry.kind === "snapshot") {
                  const s = entry.snapshot;
                  const rollbackOk = canRollback(s.reversible);
                  return (
                    <li
                      key={key}
                      className="jn-entry"
                      data-kind="snapshot"
                      data-testid={`journal-entry-${key}`}
                    >
                      <span className="jn-dot" aria-hidden />
                      <div
                        className="jn-card"
                        data-selected={selected ? "true" : "false"}
                        onClick={() => setSelectedKey(key)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setSelectedKey(key);
                          }
                        }}
                        role="button"
                        tabIndex={0}
                        aria-pressed={selected}
                      >
                        <div className="jn-card-head">
                          <div>
                            <div className="jn-badge-row">
                              <Badge variant="info">Snapshot</Badge>
                              {reversibilityBadge(s.reversible)}
                            </div>
                            <p className="jn-card-title">{sanitizeJournalCopy(s.label)}</p>
                            <p className="jn-card-meta">
                              {s.resource_type} · {s.resource_key}
                              {s.created_at ? ` · ${s.created_at}` : ""}
                            </p>
                            <p className="jn-card-note">{reversibilityCopy(s.reversible)}</p>
                          </div>
                          <Button
                            type="button"
                            variant="primary"
                            size="sm"
                            data-testid={`journal-rollback-${s.id}`}
                            disabled={busy || !rollbackOk}
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedKey(key);
                              void undo(s);
                            }}
                          >
                            {PRIMARY_CTA}
                          </Button>
                        </div>
                      </div>
                    </li>
                  );
                }
                if (entry.kind === "audit") {
                  const a = entry.audit;
                  let detail: { operation?: string; code?: string; bind_kind?: string } | null =
                    null;
                  if (a.detail_json) {
                    try {
                      detail = JSON.parse(a.detail_json) as {
                        operation?: string;
                        code?: string;
                        bind_kind?: string;
                      };
                    } catch {
                      detail = null;
                    }
                  }
                  return (
                    <li
                      key={key}
                      className="jn-entry"
                      data-kind="audit"
                      data-testid={`journal-entry-${key}`}
                    >
                      <span className="jn-dot" aria-hidden />
                      <div
                        className="jn-card"
                        data-selected={selected ? "true" : "false"}
                        onClick={() => setSelectedKey(key)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setSelectedKey(key);
                          }
                        }}
                        role="button"
                        tabIndex={0}
                        aria-pressed={selected}
                      >
                        <div className="jn-badge-row">
                          <Badge variant="default">Audit</Badge>
                        </div>
                        <p className="jn-card-meta mt-2 text-ink">
                          <span className="text-accent">{a.method}</span> {a.path} ·{" "}
                          {a.status_code}
                          {a.duration_ms != null ? ` · ${a.duration_ms}ms` : ""}
                          {a.created_at ? ` · ${a.created_at}` : ""}
                        </p>
                        {detail?.code ? (
                          <pre className="jn-audit-detail">
                            {detail.operation ?? "mutation"} · {detail.bind_kind ?? "script"}
                            {"\n"}
                            {detail.code}
                          </pre>
                        ) : null}
                      </div>
                    </li>
                  );
                }
                const run = entry.run;
                return (
                  <li
                    key={key}
                    className="jn-entry"
                    data-kind="health"
                    data-testid={`journal-entry-${key}`}
                  >
                    <span className="jn-dot" aria-hidden />
                    <div
                      className="jn-card"
                      data-selected={selected ? "true" : "false"}
                      onClick={() => setSelectedKey(key)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedKey(key);
                        }
                      }}
                      role="button"
                      tabIndex={0}
                      aria-pressed={selected}
                    >
                      <div className="jn-badge-row">
                        <Badge variant={run.broken_count > 0 ? "danger" : "success"}>
                          Health · {run.status}
                        </Badge>
                      </div>
                      <p className="jn-card-title">
                        {run.trigger === "auto" ? "Auto sweep" : "Manual sweep"}
                        {run.broken_count > 0 ? (
                          <span className="text-danger"> · {run.broken_count} broken</span>
                        ) : run.status === "complete" ? (
                          <span className="text-muted"> · {run.ok_count} succeeded</span>
                        ) : null}
                      </p>
                      <p className="jn-card-note">
                        {run.previous_version && run.current_version
                          ? `${run.previous_version} → ${run.current_version} · `
                          : ""}
                        {sanitizeJournalCopy(run.message || "")}
                        {run.finished_at ? ` · ${run.finished_at}` : ""}
                      </p>
                      {run.items.filter((i) => i.status === "broken").length > 0 ? (
                        <ul className="jn-broken-list">
                          {run.items
                            .filter((i) => i.status === "broken")
                            .map((item) => (
                              <li key={item.artifact_id}>
                                <Link href={item.deep_link}>{item.label}</Link>
                                <span className="text-muted">
                                  {" "}
                                  - {sanitizeJournalCopy(item.reason)}
                                </span>
                              </li>
                            ))}
                        </ul>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
