"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, Connection, HealthCheckRun } from "@/lib/api";
import { JobPollError, pollJob } from "@/lib/jobs";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";

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

  const variant = showBroken ? "danger" : showUpgrade ? "warning" : "info";
  const title = showBroken
    ? `${broken} broken artifact${broken === 1 ? "" : "s"} after last sweep`
    : showUpgrade
      ? `Odoo upgrade detected${
          connection?.last_seen_version && connection?.server_version
            ? ` (${connection.last_seen_version} → ${connection.server_version})`
            : ""
        }`
      : "Post-upgrade health";

  return (
    <div className={`mt-4 space-y-3 ${className}`}>
      <Callout variant={variant} title={title}>
        {showUpgrade && (
          <p>
            {isOnline
              ? "Odoo Online upgrades automatically — run a health sweep to verify your customizations still work."
              : "Re-probe detected a version change. Run a health sweep to verify tracked artifacts."}
          </p>
        )}

        {latest?.status === "running" && <p>Health sweep in progress…</p>}

        {showBroken && (
          <ul className="mt-2 space-y-1">
            {latest?.items
              .filter((i) => i.status === "broken")
              .slice(0, 5)
              .map((item) => (
                <li key={item.artifact_id}>
                  <Link href={item.deep_link} className="text-accent hover:underline">
                    {item.label}
                  </Link>
                  <span className="text-muted"> — {item.reason}</span>
                </li>
              ))}
          </ul>
        )}
        {showBroken && broken > 5 ? (
          <Link
            href={`/connections/${connectionId}/journal`}
            className="mt-2 inline-block text-accent hover:underline"
          >
            View full report in journal
          </Link>
        ) : null}

        {latest?.status === "complete" && broken === 0 && !showUpgrade && (
          <p>
            Last health sweep: {latest.ok_count} artifact{latest.ok_count === 1 ? "" : "s"}{" "}
            passed
          </p>
        )}
      </Callout>

      {error ? <ErrorNotice message={error} showDiagnose={false} /> : null}
      {notice && !error ? (
        <Callout variant="info" title="Health sweep">
          {notice}
        </Callout>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <Button type="button" variant="secondary" size="sm" disabled={busy} onClick={() => void runCheck()}>
          {busy ? "Running…" : "Run health sweep"}
        </Button>
        <Link href={`/connections/${connectionId}/journal`}>
          <Button type="button" variant="ghost" size="sm">
            Change journal
          </Button>
        </Link>
      </div>
    </div>
  );
}
