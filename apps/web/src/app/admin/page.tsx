"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Badge } from "@/components/ui/Badge";

type AdminUser = { id: string; email: string; email_verified: boolean; is_superadmin: boolean };

type WorkspaceRow = {
  id: string;
  name: string;
  slug: string;
  plan: string;
  beta_partner: boolean;
  writes_paused: boolean;
};

type TelemetryRow = {
  workspace_id: string;
  name: string;
  beta_partner: boolean;
  bulk_runs: number;
  bulk_aborts: number;
  safety_refusals: number;
  snapshot_restores: number;
  anomaly_trips: number;
};

type GaCriteria = {
  min_beta_partner_workspaces: number;
  min_weeks_per_workspace: number;
  production_write_mode_ga_unlocked: boolean;
  exit_criteria: string[];
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, { credentials: "include", ...init });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceRow[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryRow[]>([]);
  const [criteria, setCriteria] = useState<GaCriteria | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    const [u, w, t, c] = await Promise.all([
      adminFetch<AdminUser[]>("/api/admin/users"),
      adminFetch<WorkspaceRow[]>("/api/admin/workspaces"),
      adminFetch<{ workspaces: TelemetryRow[] }>("/api/admin/trust-telemetry"),
      adminFetch<GaCriteria>("/api/admin/ga-criteria"),
    ]);
    setUsers(u);
    setWorkspaces(w);
    setTelemetry(t.workspaces);
    setCriteria(c);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err instanceof Error ? err.message : "Failed to load admin"));
  }, []);

  async function toggleBeta(ws: WorkspaceRow) {
    setBusy(ws.id);
    setError(null);
    try {
      await adminFetch(`/api/admin/workspaces/${ws.id}/beta-partner`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: !ws.beta_partner,
          reason: "admin console toggle",
        }),
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Toggle failed");
    } finally {
      setBusy(null);
    }
  }

  async function toggleWritesPaused(ws: WorkspaceRow) {
    setBusy(`pause-${ws.id}`);
    setError(null);
    try {
      await adminFetch(`/api/admin/workspaces/${ws.id}/writes-paused`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          paused: !ws.writes_paused,
          reason: "admin console kill switch",
        }),
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Pause toggle failed");
    } finally {
      setBusy(null);
    }
  }

  const userColumns: DataTableColumn<AdminUser>[] = [
    { id: "email", header: "Email", accessor: (r) => r.email },
    { id: "verified", header: "Verified", accessor: (r) => (r.email_verified ? "Yes" : "No") },
    { id: "super", header: "Superadmin", accessor: (r) => (r.is_superadmin ? "Yes" : "No") },
  ];

  const wsColumns: DataTableColumn<WorkspaceRow>[] = [
    { id: "name", header: "Workspace", accessor: (r) => r.name },
    { id: "plan", header: "Plan", accessor: (r) => r.plan },
    {
      id: "beta",
      header: "Beta partner",
      accessor: (r) =>
        r.beta_partner ? <Badge variant="success">yes</Badge> : <Badge variant="info">no</Badge>,
    },
    {
      id: "paused",
      header: "Writes paused",
      accessor: (r) =>
        r.writes_paused ? <Badge variant="warning">paused</Badge> : <Badge variant="info">live</Badge>,
    },
    {
      id: "action",
      header: "",
      accessor: (r) => (
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={busy === r.id}
            onClick={() => void toggleBeta(r)}
          >
            {r.beta_partner ? "Revoke beta" : "Mark beta partner"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={r.writes_paused ? "primary" : "danger"}
            disabled={busy === `pause-${r.id}`}
            onClick={() => void toggleWritesPaused(r)}
          >
            {r.writes_paused ? "Resume writes" : "Pause writes"}
          </Button>
        </div>
      ),
    },
  ];

  const telColumns: DataTableColumn<TelemetryRow>[] = [
    { id: "name", header: "Workspace", accessor: (r) => r.name },
    {
      id: "beta",
      header: "Beta",
      accessor: (r) => (r.beta_partner ? "yes" : "no"),
    },
    { id: "runs", header: "Bulk runs", accessor: (r) => String(r.bulk_runs) },
    { id: "refusals", header: "Refusals", accessor: (r) => String(r.safety_refusals) },
    { id: "aborts", header: "Aborts", accessor: (r) => String(r.bulk_aborts) },
    { id: "restores", header: "Restores", accessor: (r) => String(r.snapshot_restores) },
    { id: "anomaly", header: "Anomaly trips", accessor: (r) => String(r.anomaly_trips) },
  ];

  return (
    <div className="space-y-6 p-6" data-testid="admin-console">
      <PageHeader
        title="Admin console"
        description="Superadmin workspace management and TRUST-9 beta evidence."
      />
      {error ? <ErrorNotice message={error} /> : null}
      {criteria ? (
        <Card className="p-4 text-sm text-muted">
          <p className="font-medium text-ink">GA criteria</p>
          <ul className="mt-2 list-disc pl-5">
            {criteria.exit_criteria.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="mt-2">
            GA unlocked: {criteria.production_write_mode_ga_unlocked ? "yes" : "no"}
          </p>
        </Card>
      ) : null}
      <Card className="p-4">
        <h2 className="mb-3 text-lg font-semibold text-ink">Users</h2>
        <DataTable columns={userColumns} rows={users} rowKey={(r) => r.id} />
      </Card>
      <Card className="p-4">
        <h2 className="mb-3 text-lg font-semibold text-ink">Workspaces</h2>
        <DataTable columns={wsColumns} rows={workspaces} rowKey={(r) => r.id} />
      </Card>
      <Card className="p-4">
        <h2 className="mb-3 text-lg font-semibold text-ink">Trust telemetry</h2>
        <DataTable columns={telColumns} rows={telemetry} rowKey={(r) => r.workspace_id} />
      </Card>
    </div>
  );
}
