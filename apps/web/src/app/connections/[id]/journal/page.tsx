"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, AuditLogRow, Connection, SnapshotRow } from "@/lib/api";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";

export default function ChangeJournalPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [audits, setAudits] = useState<AuditLogRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [conn, snaps, logs] = await Promise.all([
      api.getConnection(connectionId),
      api.listSnapshots(connectionId),
      api.listAuditLogs(80).catch(() => [] as AuditLogRow[]),
    ]);
    setConnection(conn);
    setSnapshots(snaps);
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

  return (
    <main className="odoo-shell min-h-screen px-6 py-10">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap gap-4 text-sm">
          <Link href={`/connections/${connectionId}`} className="text-[#c9a9c0] hover:underline">
            ← Metadata
          </Link>
          <Link
            href={`/connections/${connectionId}/power-ops`}
            className="text-[#8f7a88] hover:underline"
          >
            Power Ops
          </Link>
          <Link
            href={`/connections/${connectionId}/access`}
            className="text-[#8f7a88] hover:underline"
          >
            Access
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          Change journal
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]">
          Metadata snapshots with Undo · API audit (secondary)
        </p>
        <VersionAwarenessBanner capabilities={connection?.capabilities} />

        {error && <p className="mt-4 text-sm text-[#f0a8a0]">{error}</p>}
        {notice && <p className="mt-4 text-sm text-[#c9a9c0]">{notice}</p>}

        <section className="mt-8">
          <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">
            Snapshots
          </h2>
          <ul className="mt-4 space-y-3">
            {snapshots.map((s) => (
              <li
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-3 border border-[#3d2a38] bg-[#0f1a16]/70 p-4 text-sm"
              >
                <div>
                  <p className="font-medium text-[#faf6f9]">{s.label}</p>
                  <p className="mt-1 font-mono text-xs text-[#8f7a88]">
                    {s.resource_type} · {s.resource_key} · {s.reversible}
                    {s.created_at ? ` · ${s.created_at}` : ""}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={busy || s.reversible === "none"}
                  onClick={() => void undo(s.id)}
                  className="border border-[#c9a9c0] px-3 py-1.5 text-xs text-[#c9a9c0] disabled:opacity-40"
                >
                  Undo
                </button>
              </li>
            ))}
            {snapshots.length === 0 && (
              <li className="text-sm text-[#8f7a88]">
                No snapshots yet. Destructive edits (views, access, automations, Power Ops)
                create them automatically.
              </li>
            )}
          </ul>
        </section>

        <section className="mt-10">
          <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">
            API audit (filtered)
          </h2>
          <ul className="mt-4 max-h-80 space-y-2 overflow-auto text-xs">
            {audits.map((a) => (
              <li key={a.id} className="border-t border-[#1e2f29] py-2 font-mono text-[#8f7a88]">
                <span className="text-[#c9a9c0]">{a.method}</span> {a.path} · {a.status_code}
                {a.duration_ms != null ? ` · ${a.duration_ms}ms` : ""}
                {a.created_at ? ` · ${a.created_at}` : ""}
              </li>
            ))}
            {audits.length === 0 && (
              <li className="text-[#8f7a88]">No matching audit rows (auth may be off locally).</li>
            )}
          </ul>
        </section>
      </div>
    </main>
  );
}
