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
  /** False when Promote/Handoff owns the page primary CTA. */
  runIsPrimary?: boolean;
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
  runIsPrimary = true,
  onPromptChange,
  onFilesChange,
  onPlan,
  onRun,
}: JobAutopilotBriefPanelProps) {
  const empty = !prompt.trim();
  return (
    <Card className="job-brief-card p-5" data-testid="job-autopilot-brief">
      <h2 className="text-lg font-semibold tracking-tight text-ink">Job brief</h2>
      <p className="mt-1 max-w-[65ch] text-sm text-muted text-pretty">
        Who you are, what to sell or stock or invoice, country, and any residual stock
        apps do not cover. Opening this page from a built-in-apps-first Draft Studio result fills
        the brief. Nothing installs until you run Autopilot on a sandbox.
      </p>
      <div className="job-brief-composer mt-4">
        <Textarea
          className="job-brief-textarea"
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          rows={6}
          data-testid="job-brief"
          placeholder="Recording studio in Lagos. Clients book sessions. We invoice in naira. Contacts CSV attached."
        />
      </div>
      {empty ? (
        <div className="job-empty-guide mt-3" data-testid="job-brief-empty">
          <p className="job-empty-what">What: a plain-language job for a sandbox.</p>
          <p className="job-empty-why">
            Why: Autopilot plans stock Community apps first, then residual x_* only.
          </p>
          <p className="job-empty-next">
            Next: describe the job, optionally attach CSV/XLSX/PDF, then Plan packet or
            Run Autopilot.
          </p>
        </div>
      ) : null}
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
          data-testid="job-files"
        />
        {files.length ? (
          <p className="mt-1 text-xs text-muted">{files.length} file(s) selected</p>
        ) : (
          <p className="mt-1 text-xs text-muted">CSV, XLSX, or PDF. Optional for packet planning.</p>
        )}
      </div>
      <div className="job-brief-actions mt-4 flex flex-wrap items-center gap-2">
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
          variant={runBlocked || !runIsPrimary ? "secondary" : "primary"}
          className={runBlocked || !runIsPrimary ? undefined : "text-white"}
          disabled={busy !== null || runBlocked}
          loading={busy === "run"}
          onClick={onRun}
          title={runBlocked ? runBlockedReason : undefined}
          aria-disabled={runBlocked || undefined}
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
          Plan packet is read-only. Run Autopilot is the primary action: installs stock
          apps on a test copy, then smoke-tests the named process. A complete draft is not the same as certified, and neither means
          Autopilot.
        </p>
      )}
    </Card>
  );
}
