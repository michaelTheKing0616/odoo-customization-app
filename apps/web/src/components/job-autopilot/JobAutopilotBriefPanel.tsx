"use client";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { Textarea } from "@/components/ui/Textarea";
import type { JobAutopilotBusy } from "@/lib/job-autopilot-journey";

type JobAutopilotBriefPanelProps = {
  prompt: string;
  files: File[];
  busy: JobAutopilotBusy;
  runBlocked: boolean;
  runBlockedReason?: string;
  onPromptChange: (value: string) => void;
  onFilesChange: (files: File[]) => void;
  onPlan: () => void;
  onRun: () => void;
};

export function JobAutopilotBriefPanel({
  prompt,
  files,
  busy,
  runBlocked,
  runBlockedReason,
  onPromptChange,
  onFilesChange,
  onPlan,
  onRun,
}: JobAutopilotBriefPanelProps) {
  return (
    <Card className="p-5" data-testid="job-autopilot-brief">
      <h2 className="text-lg font-semibold text-ink">Job brief</h2>
      <p className="mt-1 text-sm text-muted">
        Who you are, what to sell or stock or invoice, country, and any residual stock
        apps do not cover. Opening this page from a stock-first Draft Studio result fills
        the brief. Nothing installs until you run Autopilot on a sandbox.
      </p>
      <Textarea
        className="mt-3"
        value={prompt}
        onChange={(e) => onPromptChange(e.target.value)}
        rows={6}
        data-testid="job-brief"
        placeholder="Recording studio in Lagos. Clients book sessions. We invoice in naira. Contacts CSV attached."
      />
      <div className="mt-4">
        <label className="block text-sm font-medium text-ink" htmlFor="job-files">
          Client files
        </label>
        <input
          id="job-files"
          type="file"
          multiple
          className="mt-1 block w-full text-sm text-ink"
          onChange={(e) => onFilesChange(Array.from(e.target.files ?? []))}
        />
        {files.length ? (
          <p className="mt-1 text-xs text-muted">{files.length} file(s) selected</p>
        ) : (
          <p className="mt-1 text-xs text-muted">CSV, XLSX, or PDF. Optional for packet planning.</p>
        )}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          disabled={busy !== null}
          loading={busy === "packet"}
          onClick={onPlan}
          data-testid="job-plan-packet"
        >
          Plan packet
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={busy !== null || runBlocked}
          loading={busy === "run"}
          onClick={onRun}
          title={runBlocked ? runBlockedReason : undefined}
          data-testid="job-run-autopilot"
        >
          Run Autopilot
        </Button>
      </div>
      {runBlocked ? (
        <p className="mt-2 text-xs text-muted" data-testid="job-run-blocked-hint">
          {runBlockedReason}
        </p>
      ) : (
        <p className="mt-2 text-xs text-muted">
          Plan packet is read-only. Run Autopilot installs stock apps on a sandbox, then
          RPC-smokes the named process.
        </p>
      )}
    </Card>
  );
}
