"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, Connection, HealthCheckRun } from "@/lib/api";
import { JobPollError, pollJob } from "@/lib/jobs";

type Props = {
  connectionId: string;
  connection: Connection | null;
  className?: string;
  onRefreshConnection?: () => void | Promise<void>;
};

export function HealthCheckBanner({
  connectionId,
  connection,
  className = "",
  onRefreshConnection,
}: Props) {
  const [latest, setLatest] = useState<HealthCheckRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const run = await api.getLatestHealthCheck(connectionId).catch(() => null);
    setLatest(run);
  }, [connectionId]);

  useEffect(() => {
    void refresh();
  }, [refresh, connection?.upgrade_detected]);

  async function runCheck() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const trigger = await api.runHealthCheck(connectionId, true);
      if (trigger.async_job && trigger.job_id) {
        setNotice("Health sweep running…");
        await pollJob(trigger.job_id, {
          fetchJob: (id) => api.getJob(id),
          onUpdate: (job) => {
            if (job.status === "running") {
              setNotice(`Health sweep ${job.status}…`);
            }
          },
        });
        setNotice("Health sweep complete.");
      } else if (trigger.report) {
        setLatest(trigger.report);
        setNotice(trigger.message || "Health sweep complete.");
      }
      await refresh();
      await onRefreshConnection?.();
    } catch (err) {
      if (err instanceof JobPollError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Health check failed");
      }
    } finally {
      setBusy(false);
    }
  }

  const isOnline =
    connection?.capabilities?.hosting_hint === "online" ||
    (connection?.url ?? "").includes(".odoo.com");
  const showUpgrade = Boolean(connection?.upgrade_detected);
  const broken = latest?.broken_count ?? 0;
  const showBroken = latest?.status === "complete" && broken > 0;

  if (!showUpgrade && !showBroken && !latest && !connection?.upgrade_detected) {
    return null;
  }

  return (
    <div
      className={`mt-4 space-y-3 border border-[#5a3d4a] bg-[#1a1218]/80 p-4 text-sm ${className}`}
    >
      {showUpgrade && (
        <div>
          <p className="font-medium text-[#f0c4bc]">
            Odoo upgrade detected
            {connection?.last_seen_version && connection?.server_version
              ? ` (${connection.last_seen_version} → ${connection.server_version})`
              : ""}
          </p>
          <p className="mt-1 text-[#c9a9c0]">
            {isOnline
              ? "Odoo Online upgrades automatically — run a health sweep to verify your customizations still work."
              : "Re-probe detected a version change. Run a health sweep to verify tracked artifacts."}
          </p>
        </div>
      )}

      {latest?.status === "running" && (
        <p className="text-[#c9a9c0]">Health sweep in progress…</p>
      )}

      {showBroken && (
        <div>
          <p className="font-medium text-[#f0a8a0]">
            {broken} broken artifact{broken === 1 ? "" : "s"} after last sweep
          </p>
          <ul className="mt-2 space-y-1">
            {latest?.items
              .filter((i) => i.status === "broken")
              .slice(0, 5)
              .map((item) => (
                <li key={item.artifact_id} className="text-[#c9a9c0]">
                  <Link href={item.deep_link} className="underline hover:text-[#faf6f9]">
                    {item.label}
                  </Link>
                  <span className="text-[#8f7a88]"> — {item.reason}</span>
                </li>
              ))}
          </ul>
          {broken > 5 && (
            <Link
              href={`/connections/${connectionId}/journal`}
              className="mt-2 inline-block text-[#c9a9c0] underline"
            >
              View full report in journal
            </Link>
          )}
        </div>
      )}

      {latest?.status === "complete" && broken === 0 && !showUpgrade && (
        <p className="text-[#c9a9c0]">
          Last health sweep: {latest.ok_count} artifact{latest.ok_count === 1 ? "" : "s"} OK
        </p>
      )}

      {error && <p className="text-[#f0a8a0]">{error}</p>}
      {notice && !error && <p className="text-[#c9a9c0]">{notice}</p>}

      <div className="flex flex-wrap gap-3 pt-1">
        <button
          type="button"
          disabled={busy}
          onClick={() => void runCheck()}
          className="border border-[#c9a9c0] px-3 py-1.5 text-xs text-[#c9a9c0] disabled:opacity-40"
        >
          {busy ? "Running…" : "Run health sweep"}
        </button>
        <Link
          href={`/connections/${connectionId}/journal`}
          className="border border-[#5a3d4a] px-3 py-1.5 text-xs text-[#8f7a88] hover:text-[#c9a9c0]"
        >
          Change journal
        </Link>
      </div>
    </div>
  );
}
