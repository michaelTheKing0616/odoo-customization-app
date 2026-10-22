"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, EmptyState } from "@/components/ui/layout-primitives";
import type { ConfigPacket, ConfigPacketDiff, InstanceFingerprint } from "@/lib/api";
import type { JobAutopilotBusy } from "@/lib/job-autopilot-journey";
import { checklistOpenHref } from "@/lib/odoo-urls";

type JobAutopilotConfigPanelProps = {
  configPacket: ConfigPacket | null;
  fingerprint: InstanceFingerprint | null;
  configDiff: ConfigPacketDiff | null;
  connectionUrl?: string | null;
  busy: JobAutopilotBusy;
  onFingerprint: () => void;
  onCaptureSettings: () => void;
  onDryRun: () => void;
  onApply: () => void;
  onDownload: () => void;
};

export function JobAutopilotConfigPanel({
  configPacket,
  fingerprint,
  configDiff,
  connectionUrl,
  busy,
  onFingerprint,
  onCaptureSettings,
  onDryRun,
  onApply,
  onDownload,
}: JobAutopilotConfigPanelProps) {
  const checklist = configDiff?.checklist || configPacket?.checklist || [];
  return (
    <Card className="job-config-card p-5" data-testid="job-config-packet">
      <h2 className="text-lg font-semibold tracking-tight text-ink">
        Config Packet: client replay
      </h2>
      <p className="mt-1 max-w-[65ch] text-sm text-muted text-pretty">
        Autopilot never writes production. After sandbox smoke, fingerprint the client (a
        receipt of that DB), then test run and apply with the confirm phrase. SMTP and
        payment keys stay a paste-in-Odoo checklist. This is not a live Python install.
      </p>
      {configPacket ? (
        <>
          <p className="mt-3 text-sm tabular-nums">
            sha256 {configPacket.sha256} · recipe v{configPacket.recipe_version} ·{" "}
            {configPacket.modules.length} module(s) · {configPacket.users.length} user(s)
          </p>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
            {checklist.map((item) => {
              const href = checklistOpenHref(item, connectionUrl);
              return (
                <li key={item.id}>
                  <Badge
                    variant={
                      item.status === "done"
                        ? "success"
                        : item.status === "blocked"
                          ? "danger"
                          : item.status === "secret"
                            ? "warning"
                            : "default"
                    }
                  >
                    {item.status}
                  </Badge>{" "}
                  {item.label}
                  {href ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noreferrer"
                      className="ml-2 text-xs text-accent hover:underline"
                    >
                      Open in Odoo
                    </a>
                  ) : item.href_hint ? (
                    <span className="block text-xs text-muted">{item.href_hint}</span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </>
      ) : (
        <div className="mt-4" data-testid="job-config-empty">
          <EmptyState
            title="No config summary yet"
            description="What: a replayable stock config receipt from the sandbox run. Why: so client DBs get modules, journals, and allowlisted Settings without Autopilot writing production. Next: Run Autopilot on the sandbox, then fingerprint and test run here."
          />
        </div>
      )}
      {fingerprint ? (
        <p className="mt-3 text-xs text-muted">
          Fingerprint {fingerprint.sha256}: {fingerprint.modules_installed.length} installed
          apps, {fingerprint.account_code_count} CoA codes, {fingerprint.user_logins.length}{" "}
          users.
        </p>
      ) : null}
      {configDiff ? <p className="mt-2 text-sm">Test run: {configDiff.message}</p> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          disabled={busy !== null}
          loading={busy === "fingerprint"}
          onClick={onFingerprint}
        >
          Fingerprint target
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={busy !== null}
          loading={busy === "settings"}
          onClick={onCaptureSettings}
        >
          Capture Settings
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={busy !== null || !configPacket}
          loading={busy === "dryrun"}
          onClick={onDryRun}
        >
          Test run packet
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={busy !== null || !configPacket}
          onClick={onApply}
          data-testid="job-apply-packet"
        >
          Apply packet to target
        </Button>
        <Button type="button" variant="ghost" disabled={!configPacket} onClick={onDownload}>
          Download packet JSON
        </Button>
      </div>
      {configPacket ? (
        <p className="mt-2 text-xs text-muted">
          Apply opens a confirm dialog. Secrets are never written. Promote and Apply stay
          human.
        </p>
      ) : null}
    </Card>
  );
}
