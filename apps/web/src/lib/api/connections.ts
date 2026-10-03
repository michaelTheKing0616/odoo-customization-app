import { request, CONNECTION_READ_TIMEOUT_MS } from "./client";
import type { CapabilityMatrix } from "./types-gating";
import type { Connection, ProductionReadinessReport } from "./types-schema";

export const connectionsApi = {
  listConnections: () =>
    request<Connection[]>("/api/connections", { timeoutMs: CONNECTION_READ_TIMEOUT_MS }),
  getConnection: (id: string) =>
    request<Connection>(`/api/connections/${id}`, { timeoutMs: CONNECTION_READ_TIMEOUT_MS }),
  createConnection: (body: {
    name: string;
    url: string;
    db_name: string;
    username: string;
    password: string;
    verify?: boolean;
  }) =>
    request<Connection>("/api/connections", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateConnection: (
    id: string,
    body: {
      name?: string;
      url?: string;
      db_name?: string;
      username?: string;
      password?: string;
      verify?: boolean;
    },
  ) =>
    request<Connection>(`/api/connections/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  updateConnectionWriteMode: (id: string, write_mode: Connection["write_mode"]) =>
    request<Connection>(`/api/connections/${id}/write-mode`, {
      method: "PATCH",
      body: JSON.stringify({ write_mode }),
    }),
  getProductionReadiness: (id: string) =>
    request<ProductionReadinessReport>(`/api/connections/${id}/production-readiness`),
  runProductionSnapshotDrill: (id: string) =>
    request<{ ok: boolean; snapshot_id: string; report: ProductionReadinessReport }>(
      `/api/connections/${id}/production-readiness/snapshot-drill`,
      { method: "POST" },
    ),
  confirmProductionLeastPrivilege: (id: string, acknowledge_admin: boolean) =>
    request<ProductionReadinessReport>(
      `/api/connections/${id}/production-readiness/confirm-least-privilege`,
      { method: "POST", body: JSON.stringify({ acknowledge_admin }) },
    ),
  verifyProductionBackupArtifact: (id: string) =>
    request<ProductionReadinessReport>(
      `/api/connections/${id}/production-readiness/verify-backup-artifact`,
      { method: "POST" },
    ),
  ackProductionFirstWrite: (id: string) =>
    request<ProductionReadinessReport>(
      `/api/connections/${id}/production-readiness/ack-first-write`,
      { method: "POST" },
    ),
  getSafetyContract: () => request<{ markdown: string; source: string }>("/api/trust/safety"),
  deleteConnection: (id: string) =>
    request<void>(`/api/connections/${id}`, { method: "DELETE" }),
  probeConnection: (id: string) =>
    request<{
      ok: boolean;
      uid: number | null;
      server_version: string | null;
      capabilities: CapabilityMatrix | null;
    }>(`/api/connections/${id}/probe`, { method: "POST" }),
};
