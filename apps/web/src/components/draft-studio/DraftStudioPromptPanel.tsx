"use client";

import Link from "next/link";
import { Callout } from "@/components/ui/Callout";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { DraftStudioReusePanel } from "./DraftStudioReusePanel";
import { DraftStudioApplyBar } from "./DraftStudioApplyBar";
import { createDraftHint } from "@/lib/draft-studio-journey";
import { providerSuffix } from "@/lib/wizard-ui";
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
  const reuseNeedsDecision =
    reuse.inferredReuseSuggestions.length > 0 || reuse.installableReuseSuggestions.length > 0;
  const reuseSelectedCount = reuse.reuseModels.length;

  return (
    <div className="space-y-6">
      <section
        className="draft-studio-brief"
        data-testid="draft-studio-brief"
        aria-labelledby="draft-studio-brief-title"
      >
        <h2 id="draft-studio-brief-title" className="draft-studio-brief-title">
          What should we implement?
        </h2>
        <p className="draft-studio-brief-subtitle" id="draft-studio-brief-help">
          A field on a built-in form, a feature under an existing app, or a full custom app
          workspace. Ingenium drafts a ModuleSpec{providerSuffix(aiEnabled, aiProviderLabel)}.
          Nothing writes to Odoo until you Apply.
        </p>
        {ollamaDetail ? (
          <p className="draft-studio-provider-note" data-testid="draft-provider-note">
            AI provider: {ollamaDetail}
          </p>
        ) : null}
        <div className="studio-prompt-composer draft-studio-composer">
          <label htmlFor="draft-nl-prompt" className="sr-only">
            Describe what to implement
          </label>
          <Textarea
            id="draft-nl-prompt"
            className="resize-none text-left studio-prompt-textarea"
            data-testid="draft-nl-prompt"
            value={nlPrompt}
            onChange={(e) => onPromptChange(e.target.value)}
            rows={4}
            aria-describedby="draft-studio-brief-help draft-studio-brief-status"
            placeholder="Add an SLA due date on invoices, or a law-firm practice with matters, time, and stock quotations."
          />
          <div className="studio-prompt-actions">
            <p
              className="studio-prompt-shortcut"
              id="draft-studio-brief-status"
              aria-live="polite"
            >
              {nlPrompt.trim().length < 3
                ? "A sentence or two is enough to start."
                : hint}
            </p>
          </div>
        </div>

        <div className="draft-studio-options" data-testid="draft-studio-options">
          <div className="draft-studio-options-grain">
            <Select
              label="Grain override"
              options={[
                { value: "", label: "Auto-detect" },
                { value: "field_pack", label: "Field pack" },
                { value: "feature_slice", label: "Feature under an existing app" },
                { value: "full_app", label: "Full app" },
              ]}
              value={grainOverride}
              onChange={(e) => onGrainChange(e.target.value)}
            />
            {grainLabel ? <Badge variant="info">Detected: {grainLabel}</Badge> : null}
          </div>
          <button
            type="button"
            className="draft-studio-options-toggle"
            onClick={onToggleJson}
            aria-expanded={jsonPasteOpen}
            aria-controls="draft-json-import"
            data-testid="toggle-json-import"
          >
            {jsonPasteOpen ? "Hide app-plan JSON" : "Or paste app-plan JSON"}
          </button>
        </div>

        {jsonPasteOpen ? (
          <div className="draft-studio-soft-panel mt-3 space-y-2" id="draft-json-import">
            <p className="text-xs text-muted">
              Bring your own draft JSON. We run apply-readiness (reuse wiring, live
              field naming, promo math) and load it here. Then click Apply to Odoo.
            </p>
            <Textarea
              value={jsonPaste}
              onChange={(e) => onJsonChange(e.target.value)}
              rows={6}
              className="font-mono text-xs"
              placeholder='{"technical_name":"my_app","models":[...]}'
              aria-label="App plan JSON"
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
              <label className="draft-studio-file-button">
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
                <span>Upload .json file</span>
              </label>
            </div>
          </div>
        ) : null}

        {showStudioBridge ? (
          <Callout
            variant="warning"
            title="Intent needs confirmation"
            className="mt-4"
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

        {overlapFindings.length > 0 ? (
          <section
            className="draft-studio-gate mt-4"
            data-testid="overlap-findings"
            aria-labelledby="overlap-findings-title"
          >
            <h3 id="overlap-findings-title" className="draft-studio-gate-title">
              Already exists on this instance
            </h3>
            <p className="draft-studio-gate-body">
              Choose how to proceed for each finding before you generate.
            </p>
            <ul className="draft-studio-gate-list">
              {overlapFindings.map((f) => (
                <li key={f.id}>
                  <p className="font-medium text-ink">{f.title}</p>
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
            className="draft-studio-gate mt-4"
            data-testid="connect-points-review"
            aria-labelledby="connect-points-title"
          >
            <h3 id="connect-points-title" className="draft-studio-gate-title">
              Connect points (review before draft)
            </h3>
            <p className="draft-studio-gate-body">
              Confirm the existing form and where fields go. Edit below, then approve before
              generating.
            </p>
            <div className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
              <label className="draft-studio-field">
                <span>Host model</span>
                <input
                  value={String(connectPoints.host_model ?? "")}
                  onChange={(e) => onConnectField("host_model", e.target.value)}
                  className="draft-studio-field-input font-mono"
                />
              </label>
              <label className="draft-studio-field">
                <span>Form xpath</span>
                <input
                  value={String(connectPoints.form_xpath ?? "//sheet")}
                  onChange={(e) => onConnectField("form_xpath", e.target.value)}
                  className="draft-studio-field-input font-mono"
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
                variant="secondary"
                size="sm"
                disabled={connectPointsApproved}
                onClick={onApproveConnect}
              >
                {connectPointsApproved ? "Approved" : "Approve connect points"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                loading={connectReviewBusy}
                onClick={onReviewConnect}
              >
                Re-run review
              </Button>
            </div>
          </section>
        ) : null}

        {needsConnectReview && !connectPointsApproved ? (
          <Callout variant="info" title="Component grain" className="mt-4">
            This prompt looks like a feature slice or field pack. Review connect points and
            approve before generating the draft.
          </Callout>
        ) : null}

        {showActions ? (
          <div className="draft-studio-action-dock mt-4" data-testid="draft-studio-action-dock">
            <div className="draft-studio-action-dock-primary">
              {needsConnectReview ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={connectReviewBusy || nlPrompt.trim().length < 3}
                  loading={connectReviewBusy}
                  onClick={onReviewConnect}
                  data-testid="review-connect-points"
                >
                  Review connect points
                </Button>
              ) : null}
              <DraftStudioApplyBar {...applyBar} promptLength={nlPrompt.trim().length} />
            </div>
            <div className="draft-studio-action-dock-secondary">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                loading={overlapBusy}
                disabled={nlPrompt.trim().length < 3}
                onClick={onCheckOverlap}
                data-testid="check-overlap"
              >
                Check overlap
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={!nlPrompt.trim() && !hasDraft}
                onClick={onClear}
              >
                Clear
              </Button>
            </div>
          </div>
        ) : null}

        {connectPoints && !needsConnectReview ? (
          <p className="draft-studio-quiet-note mt-3">
            Full-app draft. Connect points are not required.
          </p>
        ) : null}

        <details
          className="draft-studio-disclosure draft-studio-reuse-disclosure mt-6"
          open={reuseNeedsDecision || undefined}
          data-testid="draft-studio-reuse-disclosure"
        >
          <summary>
            <span>Reuse existing Odoo models</span>
            <span className="draft-studio-disclosure-meta">
              {reuseSelectedCount > 0 ? `${reuseSelectedCount} selected` : "Optional"}
            </span>
          </summary>
          <DraftStudioReusePanel {...reuse} />
        </details>

        {gallery.length > 0 ? (
          <details className="draft-studio-disclosure mt-3" data-testid="draft-studio-gallery">
            <summary>
              <span>Start from a component</span>
              <span className="draft-studio-disclosure-meta">{gallery.length}</span>
            </summary>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {gallery.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => onSelectGallery(c)}
                  aria-pressed={selectedGalleryId === c.id}
                  className={`draft-studio-gallery-item${
                    selectedGalleryId === c.id ? " is-selected" : ""
                  }`}
                >
                  <span className="font-semibold text-ink">{c.name}</span>
                  <span className="mt-1 block text-xs text-muted">{c.description}</span>
                  <span className="mt-1 block font-mono text-[11px] text-muted">
                    Host: {c.host_slot}
                  </span>
                </button>
              ))}
            </div>
          </details>
        ) : null}
      </section>
    </div>
  );
}

export type { ReuseModelRow, ReuseDecisionChip };
