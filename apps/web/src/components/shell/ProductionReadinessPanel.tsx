"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, Connection, ProductionReadinessReport } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/layout-primitives";
import { ErrorNotice } from "@/components/ui/ErrorNotice";

type Props = {
  connection: Connection;
  onRefreshConnection?: () => Promise<void>;
};

function statusBadge(status: "pass" | "fail" | "warn") {
  if (status === "pass") return <Badge variant="success">pass</Badge>;
  if (status === "warn") return <Badge variant="warning">warn</Badge>;
  return <Badge variant="danger">fail</Badge>;
}

export function ProductionReadinessPanel({ connection, onRefreshConnection }: Props) {
  const [report, setReport] = useState<ProductionReadinessReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ackAdmin, setAckAdmin] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setReport(await api.getProductionReadiness(connection.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load checklist");
    }
  }, [connection.id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function runDrill() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.runProductionSnapshotDrill(connection.id);
      setReport(res.report);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Drill failed");
    } finally {
      setBusy(false);
    }
  }

  async function confirmLeastPrivilege() {
    setBusy(true);
    setError(null);
    try {
      setReport(await api.confirmProductionLeastPrivilege(connection.id, ackAdmin));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirm failed");
    } finally {
      setBusy(false);
    }
  }

  async function verifyArtifact() {
    setBusy(true);
    setError(null);
    try {
      setReport(await api.verifyProductionBackupArtifact(connection.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verify failed");
    } finally {
      setBusy(false);
    }
  }

  const drillId = report?.drill_snapshot_id;
  const artifactUrl = drillId
    ? `/api/connections/${connection.id}/snapshots/${drillId}/artifact.csv`
    : null;

  return (
    <Callout
      variant={report?.passed ? "info" : "warning"}
      title="Production readiness checklist"
      testId="production-readiness-panel"
      className="mt-4"
    >
      <p className="text-sm">
        Required before enabling <strong>production</strong> write mode.{" "}
        <Link href="/settings/trust-safety" className="text-accent hover:underline">
          Read the safety contract
        </Link>
        .
      </p>
      {error ? <ErrorNotice message={error} className="mt-3" /> : null}
      {report ? (
        <ul className="mt-3 space-y-2">
          {report.items.map((item) => (
            <li key={item.key}>
              <Card className="flex flex-wrap items-start justify-between gap-2 p-3 text-sm">
                <div>
                  <span className="font-medium text-ink">{item.label}</span>
                  <p className="mt-1 text-muted">{item.detail}</p>
                </div>
                {statusBadge(item.status)}
              </Card>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-muted">Loading checklist…</p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button type="button" size="sm" disabled={busy} onClick={() => void runDrill()}>
          Run snapshot drill
        </Button>
        {artifactUrl ? (
          <Button type="button" size="sm" variant="secondary" asChild>
            <a href={artifactUrl} download data-testid="download-drill-artifact">
              Download drill CSV
            </a>
          </Button>
        ) : null}
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={busy || !drillId}
          onClick={() => void verifyArtifact()}
        >
          Mark artifact verified
        </Button>
        <label className="flex items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={ackAdmin}
            onChange={(e) => setAckAdmin(e.target.checked)}
          />
          Acknowledge admin-user warning
        </label>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={busy}
          onClick={() => void confirmLeastPrivilege()}
        >
          Confirm least-privilege user
        </Button>
        {onRefreshConnection ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              setError(null);
              void onRefreshConnection()
                .then(() => load())
                .catch((err) =>
                  setError(err instanceof Error ? err.message : "Refresh failed"),
                )
                .finally(() => setBusy(false));
            }}
          >
            Refresh probe / health
          </Button>
        ) : null}
      </div>
      {report?.passed ? (
        <p className="mt-3 text-sm text-ink" data-testid="production-readiness-passed">
          Checklist complete — production write mode can be enabled.
        </p>
      ) : null}
    </Callout>
  );
}
