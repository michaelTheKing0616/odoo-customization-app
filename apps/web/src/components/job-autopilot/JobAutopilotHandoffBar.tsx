"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import type { Connection } from "@/lib/api";
import type { JobAutopilotBusy } from "@/lib/job-autopilot-journey";

type JobAutopilotHandoffBarProps = {
  connectionId: string;
  targets: Connection[];
  targetId: string;
  sandboxUrl: string | null;
  sandboxLabel: string;
  hasResult: boolean;
  promoteReady: boolean;
  hasResidualZip: boolean;
  showModuleSpec: boolean;
  busy: JobAutopilotBusy;
  onTargetChange: (id: string) => void;
  onPromote: () => void;
  onDownloadReport: () => void;
  onDownloadPdf: () => void;
};

export function JobAutopilotHandoffBar({
  connectionId,
  targets,
  targetId,
  sandboxUrl,
  sandboxLabel,
  hasResult,
  promoteReady,
  hasResidualZip,
  showModuleSpec,
  busy,
  onTargetChange,
  onPromote,
  onDownloadReport,
  onDownloadPdf,
}: JobAutopilotHandoffBarProps) {
  return (
    <Card className="p-5" data-testid="job-handoff-bar">
      <h2 className="text-lg font-semibold text-ink">Promote and handoff</h2>
      <p className="mt-1 text-sm text-muted">
        Autopilot never writes production. Promote stays a human step onto another
        connection. Stock-only jobs hand off the sandbox itself.
      </p>
      <label className="mt-4 block text-sm text-ink">
        Promote target
        <select
          className="mt-1 block min-w-[16rem] rounded border border-line bg-surface px-2 py-1 text-sm"
          value={targetId}
          onChange={(e) => onTargetChange(e.target.value)}
          data-testid="job-promote-target"
        >
          <option value="">Select another connection…</option>
          {targets.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.write_mode})
            </option>
          ))}
        </select>
      </label>
      <div className="job-handoff-bar mt-4">
        {sandboxUrl ? (
          <Button asChild>
            <a href={sandboxUrl} target="_blank" rel="noreferrer">
              {sandboxLabel}
            </a>
          </Button>
        ) : null}
        <Button
          type="button"
          variant="secondary"
          disabled={!promoteReady || busy !== null}
          onClick={onPromote}
          data-testid="job-promote-or-handoff"
        >
          {hasResidualZip ? "Promote to target" : "Handoff"}
        </Button>
        <Button type="button" variant="ghost" disabled={!hasResult} onClick={onDownloadReport}>
          Download markdown
        </Button>
        <Button
          type="button"
          variant="ghost"
          disabled={!hasResult || busy !== null}
          loading={busy === "pdf"}
          onClick={onDownloadPdf}
        >
          Download PDF
        </Button>
        <Button asChild variant="ghost">
          <Link href={`/connections/${connectionId}/wizard`}>Draft Studio</Link>
        </Button>
        <Button asChild variant="ghost">
          <Link href={`/connections/${connectionId}/studio`}>App Studio</Link>
        </Button>
        {showModuleSpec ? (
          <Button asChild variant="ghost">
            <Link href={`/connections/${connectionId}/modulespec`}>ModuleSpec</Link>
          </Button>
        ) : null}
      </div>
    </Card>
  );
}
