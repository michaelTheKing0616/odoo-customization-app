"use client";

import { useState } from "react";
import { StageProgress } from "@/components/progress/StageProgress";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { Callout } from "@/components/ui/Callout";
import { api } from "@/lib/api";
import { newProgressRunId } from "@/lib/progress/run-id";

/** Dashboard Studio shell — charts and persistence ship in T4-DASH; progress is wired (T4-PROG). */
export default function DashboardStudioPage() {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function preview() {
    const q = prompt.trim();
    if (!q || busy) return;
    const progressRunId = newProgressRunId("dash");
    setRunId(progressRunId);
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const out = await api.dashboardPreview({ prompt: q, progress_run_id: progressRunId });
      setRunId(out.run_id);
      setMessage(out.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8" data-testid="dashboard-studio-page">
      <PageHeader
        title="Dashboard Studio"
        description="Describe the numbers you need. Dashboards only read data, and protected records are left out."
      />
      <Card className="mt-6 space-y-4 p-5">
        <Input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. Top 5 customers by revenue this month"
          aria-label="Dashboard prompt"
          data-testid="dashboard-studio-prompt"
        />
        <Button
          type="button"
          variant="primary"
          disabled={busy || !prompt.trim()}
          onClick={() => void preview()}
          data-testid="dashboard-studio-generate"
        >
          {busy ? "Planning…" : "Generate preview"}
        </Button>
        {busy ? (
          <StageProgress
            runId={runId}
            active
            fallbackLabel="Planning dashboard…"
            onStop={() => setBusy(false)}
          />
        ) : null}
        {error ? (
          <Callout variant="danger" title="Preview failed">
            {error}
          </Callout>
        ) : null}
        {message ? (
          <Callout variant="info" title="Preview status">
            {message}
          </Callout>
        ) : null}
      </Card>
    </div>
  );
}
