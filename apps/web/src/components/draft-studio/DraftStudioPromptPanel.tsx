"use client";

import Link from "next/link";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/layout-primitives";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { DraftStudioReusePanel } from "./DraftStudioReusePanel";
import { DraftStudioApplyBar } from "./DraftStudioApplyBar";
import { createDraftHint } from "@/lib/draft-studio-journey";
import { stashPromptForStudio } from "@/lib/studio-session";
import type { ReuseModelRow } from "@/lib/api";
import type { ReuseDecisionChip } from "@/lib/reuse-chips";

export type OverlapFinding = {
  id: string;
  title: string;
  evidence: string;
  deep_link?: string | null;
  extend_host_model?: string | null;
};

export type GalleryItem = {
  id: string;
  name: string;
  description: string;
  host_slot: string;
};

type DraftStudioPromptPanelProps = {
  connectionId: string;
  nlPrompt: string;
  aiEnabled: boolean;
  aiProviderLabel: string;
  ollamaDetail: string | null;
  grainOverride: string;
  grainLabel: string | null;
  jsonPasteOpen: boolean;
  jsonPaste: string;
  jsonBusy: boolean;
  busy: boolean;
  overlapFindings: OverlapFinding[];
  overlapChoice: string | null;
  overlapBusy: boolean;
  overlapResolved: boolean;
  connectPoints: Record<string, unknown> | null;
  needsConnectReview: boolean;
  connectPointsApproved: boolean;
  connectReviewBusy: boolean;
  hostCandidates: Array<{ model: string; label: string; score: number; reason?: string }>;
  gallery: GalleryItem[];
  selectedGalleryId: string;
  showStudioBridge: boolean;
  hasDraft: boolean;
  isFullAppGrain: boolean;
  showActions?: boolean;
  applyBar: React.ComponentProps<typeof DraftStudioApplyBar>;
  reuse: React.ComponentProps<typeof DraftStudioReusePanel>;
  onPromptChange: (value: string) => void;
  onToggleJson: () => void;
  onJsonChange: (value: string) => void;
  onLoadJson: () => void;
  onUploadJson: (file: File) => void;
  onGrainChange: (value: string) => void;
  onOverlapUse: (finding: OverlapFinding) => void;
  onOverlapExtend: (finding: OverlapFinding) => void;
  onOverlapBuildAnyway: (id: string) => void;
  onConnectField: (key: string, value: string) => void;
  onApproveConnect: () => void;
  onReviewConnect: () => void;
  onCheckOverlap: () => void;
  onSelectGallery: (item: GalleryItem) => void;
  onClear: () => void;
};

export function DraftStudioPromptPanel({
  connectionId,
  nlPrompt,
  aiEnabled,
  aiProviderLabel,
  ollamaDetail,
  grainOverride,
  grainLabel,
  jsonPasteOpen,
  jsonPaste,
  jsonBusy,
  busy,
  overlapFindings,
  overlapChoice,
  overlapBusy,
  overlapResolved,
  connectPoints,
  needsConnectReview,
  connectPointsApproved,
  connectReviewBusy,
  hostCandidates,
  gallery,
  selectedGalleryId,
  showStudioBridge,
  hasDraft,
  isFullAppGrain,
  showActions = true,
  applyBar,
  reuse,
  onPromptChange,
  onToggleJson,
  onJsonChange,
  onLoadJson,
  onUploadJson,
  onGrainChange,
  onOverlapUse,
  onOverlapExtend,
  onOverlapBuildAnyway,
  onConnectField,
  onApproveConnect,
  onReviewConnect,
  onCheckOverlap,
  onSelectGallery,
  onClear,
}: DraftStudioPromptPanelProps) {
  const hint = createDraftHint({
    hasDraft,
    promptLength: nlPrompt.trim().length,
    needsConnectReview,
    connectReady: Boolean(connectPointsApproved && connectPoints),
    overlapPending: overlapFindings.length > 0 && !overlapResolved,
    isFullAppGrain,
  });

  return (
    <div className="space-y-6">
      {gallery.length > 0 ? (
        <Card className="p-5">
          <h2 className="text-lg font-semibold text-ink">Component gallery</h2>
          <p className="mt-1 text-xs text-muted">
            Reusable slices that attach to stock or custom hosts.
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {gallery.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => onSelectGallery(c)}
                className={`rounded-md border p-3 text-left text-sm transition ${
                  selectedGalleryId === c.id
                    ? "border-accent bg-accent-subtle"
                    : "border-border-subtle hover:bg-surface-muted"
                }`}
              >
                <span className="font-semibold text-ink">{c.name}</span>
                <span className="mt-1 block text-xs text-muted">{c.description}</span>
                <span className="mt-1 block font-mono text-[10px] text-accent">
                  Host: {c.host_slot}
                </span>
              </button>
            ))}
          </div>
        </Card>
      ) : null}

      <Card className="p-5">
        <h2 className="text-lg font-semibold text-ink">What should we implement?</h2>
        <p className="mt-1 text-sm text-muted">
          Same bar as a senior Odoo team: a field pack on a stock form, a feature under an
          existing app, or a full residual workspace. AI drafts a{" "}
          <strong className="font-medium text-ink">ModuleSpec</strong> (
          {aiEnabled ? `${aiProviderLabel} on` : "AI off"}
          {ollamaDetail ? ` · ${ollamaDetail}` : ""}
          ). Nothing is written to Odoo until you click{" "}
          <strong className="font-medium text-ink">Apply to Odoo</strong>.
        </p>
        <Textarea
          className="mt-3"
          data-testid="draft-nl-prompt"
          value={nlPrompt}
          onChange={(e) => onPromptChange(e.target.value)}
          rows={3}
          placeholder="Add SLA due date on invoices — or a law-firm practice with matters, time, and stock quotations…"
        />
        {showStudioBridge ? (
          <Callout
            variant="warning"
            title="Intent needs confirmation"
            className="mt-3"
            testId="wizard-studio-bridge"
          >
            <p className="text-sm">
              App Studio can ask one clarifying question before generation so the wrong
              vertical pack is not merged silently.
            </p>
            <Link
              href={`/connections/${connectionId}/studio`}
              className="mt-2 inline-flex text-sm font-medium text-accent underline"
              onClick={() => {
                if (nlPrompt.trim()) stashPromptForStudio(connectionId, nlPrompt.trim());
              }}
            >
              Open in App Studio
            </Link>
          </Callout>
        ) : null}

        <div className="mt-4 rounded-md border border-border-subtle bg-surface-muted p-3">
          <button
            type="button"
            className="flex w-full items-center justify-between text-left text-sm font-medium text-ink"
            onClick={onToggleJson}
            data-testid="toggle-json-import"
          >
            <span>Or paste ModuleSpec JSON</span>
            <span className="text-xs text-muted">{jsonPasteOpen ? "Hide" : "Show"}</span>
          </button>
          {jsonPasteOpen ? (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-muted">
                Bring your own draft JSON — we run apply-readiness (reuse wiring, live
                field naming, promo math) and load it here. Then click Apply to Odoo.
              </p>
              <Textarea
                value={jsonPaste}
                onChange={(e) => onJsonChange(e.target.value)}
                rows={6}
                className="font-mono text-xs"
                placeholder='{"technical_name":"my_app","models":[...]}'
                data-testid="json-paste-input"
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  loading={jsonBusy}
                  disabled={busy}
                  onClick={onLoadJson}
                  data-testid="load-json-draft"
                >
                  Load JSON draft
                </Button>
                <label className="inline-flex cursor-pointer items-center">
                  <input
                    type="file"
                    accept=".json,application/json"
                    className="sr-only"
                    data-testid="json-file-input"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) onUploadJson(file);
                      e.target.value = "";
                    }}
                  />
                  <span className="inline-flex h-8 items-center rounded-md border border-border-subtle px-3 text-xs text-ink hover:bg-surface-raised">
                    Upload .json file
                  </span>
                </label>
              </div>
            </div>
          ) : null}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Select
            label="Grain override"
            options={[
              { value: "", label: "Auto-detect" },
              { value: "field_pack", label: "Field pack" },
              { value: "feature_slice", label: "Component / feature slice" },
              { value: "full_app", label: "Full app" },
            ]}
            value={grainOverride}
            onChange={(e) => onGrainChange(e.target.value)}
          />
          {grainLabel ? <Badge variant="info">Detected: {grainLabel}</Badge> : null}
        </div>

        {overlapFindings.length > 0 ? (
          <section
            className="mt-4 space-y-3 rounded-md border border-border-subtle bg-surface-muted p-4"
            data-testid="overlap-findings"
          >
            <h3 className="text-sm font-semibold text-ink">Already exists on this instance</h3>
            <p className="text-xs text-muted">
              Review before drafting — choose how to proceed for each finding.
            </p>
            <ul className="space-y-3">
              {overlapFindings.map((f) => (
                <li key={f.id} className="border-b border-border-subtle pb-3 text-sm">
                  <p className="font-medium">{f.title}</p>
                  <p className="mt-1 text-xs text-muted">{f.evidence}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {f.deep_link ? (
                      <Button type="button" size="sm" variant="secondary" onClick={() => onOverlapUse(f)}>
                        Use what exists
                      </Button>
                    ) : null}
                    {f.extend_host_model ? (
                      <Button type="button" size="sm" variant="secondary" onClick={() => onOverlapExtend(f)}>
                        Extend it
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => onOverlapBuildAnyway(f.id)}
                    >
                      Build anyway
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
            {overlapChoice === "build_anyway" ? (
              <Callout variant="warning" title="Building anyway">
                Your choice is recorded on the draft audit trail.
              </Callout>
            ) : null}
          </section>
        ) : null}

        {connectPoints && needsConnectReview ? (
          <section
            className="mt-4 rounded-md border border-border-subtle bg-surface-muted p-4"
            data-testid="connect-points-review"
          >
            <h3 className="text-sm font-semibold text-ink">Connect points (review before draft)</h3>
            <p className="mt-1 text-xs text-muted">
              Confirm host model and form placement. Edit below, then approve before drafting.
            </p>
            <div className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
              <label>
                Host model
                <input
                  value={String(connectPoints.host_model ?? "")}
                  onChange={(e) => onConnectField("host_model", e.target.value)}
                  className="mt-1 w-full rounded border border-border-subtle bg-surface px-2 py-1 font-mono"
                />
              </label>
              <label>
                Form xpath
                <input
                  value={String(connectPoints.form_xpath ?? "//sheet")}
                  onChange={(e) => onConnectField("form_xpath", e.target.value)}
                  className="mt-1 w-full rounded border border-border-subtle bg-surface px-2 py-1 font-mono"
                />
              </label>
            </div>
            {hostCandidates.length > 1 ? (
              <p className="mt-2 text-xs text-muted">
                Other hosts:{" "}
                {hostCandidates
                  .slice(1, 4)
                  .map((h) => `${h.label} (${h.model})`)
                  .join(" · ")}
              </p>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                type="button"
                variant="primary"
                size="sm"
                disabled={connectPointsApproved}
                onClick={onApproveConnect}
              >
                {connectPointsApproved ? "Approved" : "Approve connect points"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                loading={connectReviewBusy}
                onClick={onReviewConnect}
              >
                Re-run review
              </Button>
            </div>
          </section>
        ) : null}

        <DraftStudioReusePanel {...reuse} />

        {showActions ? (
        <div className="mt-4 space-y-3 rounded-md border border-border-subtle bg-surface-muted p-4">
          <p className="text-sm font-medium text-ink">What to click</p>
          <div className="flex flex-wrap items-center gap-2">
            {needsConnectReview ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={connectReviewBusy || nlPrompt.trim().length < 3}
                loading={connectReviewBusy}
                onClick={onReviewConnect}
                data-testid="review-connect-points"
              >
                Review connect points
              </Button>
            ) : null}
            <DraftStudioApplyBar {...applyBar} />
          </div>
          <p className="text-xs text-muted">{hint}</p>
          <div className="flex flex-wrap gap-2 border-t border-border-subtle pt-3">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              loading={overlapBusy}
              disabled={nlPrompt.trim().length < 3}
              onClick={onCheckOverlap}
              data-testid="check-overlap"
            >
              Check overlap
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={onClear}>
              Clear
            </Button>
          </div>
        </div>
        ) : null}
        {needsConnectReview && !connectPointsApproved ? (
          <Callout variant="info" title="Component grain" className="mt-3">
            This prompt looks like a feature slice or field pack — review connect points and
            approve before creating the draft.
          </Callout>
        ) : null}
        {connectPoints && !needsConnectReview ? (
          <section className="mt-4 rounded-md border border-border-subtle bg-surface p-4">
            <h3 className="text-sm font-semibold text-muted">Connect points</h3>
            <p className="mt-1 text-xs text-muted">Full-app draft — connect points not required.</p>
          </section>
        ) : null}
      </Card>
    </div>
  );
}

export type { ReuseModelRow, ReuseDecisionChip };
