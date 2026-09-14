"use client";

import Link from "next/link";
import { Callout } from "@/components/ui/Callout";
import { Button } from "@/components/ui/Button";
import { HostInstallPanel } from "@/components/studio/HostInstallDialog";
import type { DraftBanner } from "@/lib/draft-studio-banners";
import type { HostInstallOffer, StockAppRow } from "@/lib/draft-form-preview";
import type { AuthoringFinding } from "@/lib/draft-form-preview";
import type { OperatorSurface } from "@/lib/operator-surface";
import type { ProtectedModuleRefusal } from "@/lib/api";
import { operatorSurfaceHasPlacement } from "@/lib/operator-surface";

type ClarifyOption = { id: string; label: string };

type DraftStudioHonestyBannersProps = {
  connectionId: string;
  liveApplyBanner: DraftBanner | null;
  unfinishedBanner: DraftBanner | null;
  generateUiBlocked: string | null;
  aiNote: string | null;
  genUiResult: string | null;
  odooAppUrl: string | null;
  llmStatusBanner: string | null;
  llmStatusMode?: string;
  retryDisabled: boolean;
  showRetry: boolean;
  aiBusy: boolean;
  operatorBrief?: {
    formatted?: string;
    capability_path?: string;
    ir_confidence?: string;
    unknowns?: string[];
  } | null;
  refuseClone: boolean;
  refuseHonesty?: string | null;
  generationHonesty?: string | null;
  operatorSurface: OperatorSurface | null;
  stockReuse: boolean;
  stockApps: StockAppRow[];
  jobAutopilotHref: string;
  clarifyQuestion?: string | null;
  clarifyOptions?: ClarifyOption[];
  clarifyDefaultId?: string;
  draftNeedsRegenerate: boolean;
  canDraft: boolean;
  warnings: string[];
  authoredOptionA: boolean;
  authoringPassed: boolean;
  hostInstallOffers: HostInstallOffer[];
  leftoverAuthoringFindings: AuthoringFinding[];
  isOdooOnline: boolean;
  optionALines: string[];
  capabilityPrimaryOptionA: boolean;
  goLiveReady: boolean;
  zipLocked: boolean;
  optionAProveBusy: boolean;
  optionAProveNote: string | null;
  computeSuggestions: Array<{ model?: string; message?: string }>;
  refusals: ProtectedModuleRefusal[];
  snapshots: Array<{ id: string; summary: string; updated_at: string | null }>;
  onRetryEnrichment: () => void;
  onRegenerate: () => void;
  onStashJobBrief: () => void;
  onInstallHost: (offer: HostInstallOffer, phrase: string) => void;
  onProveOptionA: () => void;
  onRestoreSnapshot: (id: string) => void;
  onLoadWalkthrough: () => void;
};

export function DraftStudioHonestyBanners({
  connectionId,
  liveApplyBanner,
  unfinishedBanner,
  generateUiBlocked,
  aiNote,
  genUiResult,
  odooAppUrl,
  llmStatusBanner,
  llmStatusMode,
  retryDisabled,
  showRetry,
  aiBusy,
  operatorBrief,
  refuseClone,
  refuseHonesty,
  generationHonesty,
  operatorSurface,
  stockReuse,
  stockApps,
  jobAutopilotHref,
  clarifyQuestion,
  clarifyOptions,
  clarifyDefaultId,
  draftNeedsRegenerate,
  canDraft,
  warnings,
  authoredOptionA,
  authoringPassed,
  hostInstallOffers,
  leftoverAuthoringFindings,
  isOdooOnline,
  optionALines,
  capabilityPrimaryOptionA,
  goLiveReady,
  zipLocked,
  optionAProveBusy,
  optionAProveNote,
  computeSuggestions,
  refusals,
  snapshots,
  onRetryEnrichment,
  onRegenerate,
  onStashJobBrief,
  onInstallHost,
  onProveOptionA,
  onRestoreSnapshot,
  onLoadWalkthrough,
}: DraftStudioHonestyBannersProps) {
  return (
    <div className="studio-banner-stack">
      {generateUiBlocked ? (
        <Callout variant="warning" title="Apply to Odoo blocked">
          {generateUiBlocked}
        </Callout>
      ) : null}
      {liveApplyBanner ? (
        <Callout variant="warning" title={liveApplyBanner.title} testId={liveApplyBanner.testId}>
          {liveApplyBanner.body}
        </Callout>
      ) : null}
      {unfinishedBanner ? (
        <Callout variant="warning" title={unfinishedBanner.title} testId={unfinishedBanner.testId}>
          {unfinishedBanner.body}
        </Callout>
      ) : null}
      {aiNote ? (
        <Callout variant="info" title="Note">
          {aiNote}
        </Callout>
      ) : null}
      {genUiResult ? (
        <Callout variant="info" title="Applied to Odoo" className="studio-callout-success-tone">
          <p>{genUiResult}</p>
          {odooAppUrl ? (
            <p className="mt-2 flex flex-wrap items-center gap-2">
              <Button asChild variant="primary" size="sm">
                <a
                  href={odooAppUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  data-testid="open-app-in-odoo"
                >
                  Open app in Odoo
                </a>
              </Button>
              <span className="text-xs text-muted">
                Opens the app root. Use Operations, Inventory, and People — not a
                per-model list.
              </span>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                data-testid="load-demo-walkthrough"
                onClick={onLoadWalkthrough}
              >
                Load demo walkthrough
              </Button>
            </p>
          ) : null}
        </Callout>
      ) : null}
      {snapshots.length > 0 ? (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted">Saved snapshots</p>
          <p className="text-[11px] text-muted">
            Clicking a row replaces the current JSON. It does not run Expert review.
          </p>
          <ul className="mt-1 space-y-1">
            {snapshots.slice(0, 5).map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  className="text-left text-xs text-muted underline hover:text-ink"
                  onClick={() => onRestoreSnapshot(c.id)}
                >
                  {c.summary}
                  {c.updated_at ? ` · ${new Date(c.updated_at).toLocaleString()}` : ""}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {llmStatusBanner || showRetry ? (
        <Callout
          variant={llmStatusMode === "llm_full" && retryDisabled ? "info" : llmStatusBanner ? "warning" : "info"}
          title="AI draft status"
          testId="retry-ai-enrichment"
        >
          <p className="text-sm">
            {llmStatusBanner ||
              "Retry AI enrichment wakes Flash/local/cloud, re-runs missed polish, and completes residual hygiene from your brief."}
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="mt-2"
            disabled={retryDisabled}
            loading={aiBusy}
            title={
              retryDisabled && !aiBusy
                ? "Enrichment already completed successfully"
                : "Wake AI providers and re-run missed polish / residual hygiene"
            }
            onClick={onRetryEnrichment}
            data-testid="retry-ai-enrichment-btn"
          >
            Retry AI enrichment
          </Button>
        </Callout>
      ) : null}
      {operatorBrief?.formatted ? (
        <Callout
          variant="info"
          title={`Structured brief${
            operatorBrief.capability_path ? ` · ${operatorBrief.capability_path}` : ""
          }`}
          testId="operator-brief"
        >
          <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-ink">
            {operatorBrief.formatted}
          </pre>
          {operatorBrief.unknowns?.length ? (
            <p className="mt-2 text-xs text-muted">
              Unknowns (not assumed): {operatorBrief.unknowns.join("; ")}
            </p>
          ) : null}
        </Callout>
      ) : null}
      {refuseClone ? (
        <Callout
          variant="warning"
          title="Not generated — Apps Store clone refused"
          testId="generation-refuse-clone"
        >
          <p className="text-sm">
            {refuseHonesty ||
              "This platform does not clone Apps Store or GM modules. Describe the residual process, or ask for the honest POS receipt options template."}
          </p>
        </Callout>
      ) : null}
      {!refuseClone && generationHonesty ? (
        <Callout variant="info" title="Honest capability" testId="generation-honesty">
          <p className="text-sm">{generationHonesty}</p>
        </Callout>
      ) : null}
      {operatorSurfaceHasPlacement(operatorSurface) && operatorSurface ? (
        <Callout variant="info" title="Where this app shows up" testId="operator-surface">
          {operatorSurface.summary ? <p className="text-sm">{operatorSurface.summary}</p> : null}
          {operatorSurface.app_menu?.label ? (
            <p className="mt-2 text-sm">
              <span className="font-medium">App menu:</span> {operatorSurface.app_menu.label}
              {operatorSurface.app_menu.technical_name ? (
                <span className="font-mono text-xs text-muted">
                  {" "}
                  ({operatorSurface.app_menu.technical_name})
                </span>
              ) : null}
            </p>
          ) : null}
          {operatorSurface.host_buttons.length > 0 ? (
            <div className="mt-2">
              <p className="text-sm font-medium">Smart buttons on stock apps</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                {operatorSurface.host_buttons.map((b) => (
                  <li key={`${b.host_model}:${b.residual_model}:${b.button_label}`}>
                    «{b.button_label}» on {b.host_label}{" "}
                    <span className="font-mono text-xs text-muted">({b.host_model})</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {operatorSurface.residual_buttons.length > 0 ? (
            <div className="mt-2">
              <p className="text-sm font-medium">Smart buttons on this app</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                {operatorSurface.residual_buttons.map((b) => (
                  <li key={`${b.on_model}:${b.related_model}:${b.button_label}`}>
                    «{b.button_label}» on{" "}
                    <span className="font-mono text-xs">{b.on_model}</span> →{" "}
                    <span className="font-mono text-xs">{b.related_model}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {operatorSurface.stock_links.length > 0 ? (
            <div className="mt-2">
              <p className="text-sm font-medium">Stock links on the form</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                {operatorSurface.stock_links.map((l) => (
                  <li key={`${l.on_model}:${l.field}`}>
                    {l.field_label} → {l.stock_label}{" "}
                    <span className="font-mono text-xs text-muted">({l.stock_model})</span>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-xs text-muted">
                These stay as form fields — not duplicate smart buttons next to the
                many2one.
              </p>
            </div>
          ) : null}
        </Callout>
      ) : null}
      {stockReuse && stockApps.length > 0 ? (
        <Callout
          variant="info"
          title="Community apps covering this brief"
          testId="stock-reuse-apps"
        >
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {stockApps.map((app) => (
              <li key={app.id}>
                {app.label} <span className="font-mono text-xs text-muted">({app.id})</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-sm text-muted">
            Empty models/views is the correct ModuleSpec — stock already covers cashiers,
            quotations, and invoices. Completeness 10.0 is hygiene on an empty spec, not
            a shippable custom app.
          </p>
          <Link
            href={jobAutopilotHref}
            className="mt-2 inline-flex text-sm font-medium text-accent underline"
            onClick={onStashJobBrief}
          >
            Open Job Autopilot for sandbox install and quote→invoice smoke
          </Link>
        </Callout>
      ) : null}
      {clarifyQuestion ? (
        <Callout variant="warning" title="One question" testId="generation-clarify">
          <p className="text-sm">{clarifyQuestion}</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {(clarifyOptions || []).map((opt) => (
              <li key={opt.id}>
                {opt.label}
                {clarifyDefaultId === opt.id ? " (default)" : ""}
              </li>
            ))}
          </ul>
        </Callout>
      ) : null}
      {draftNeedsRegenerate && !llmStatusBanner && !stockReuse ? (
        <Callout variant="warning" title="Generic placeholders in this draft">
          <p className="text-sm">
            The AI model timed out — generic placeholders filled the gaps. Regenerate for
            domain-specific results.
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="mt-2"
            disabled={aiBusy || !canDraft}
            loading={aiBusy}
            onClick={onRegenerate}
            data-testid="regenerate-draft"
          >
            Regenerate
          </Button>
        </Callout>
      ) : null}
      {warnings.length > 0 ? (
        <Callout variant="warning" title="Draft warnings">
          <ul className="list-disc space-y-1 pl-5">
            {warnings.slice(0, 12).map((w, i) => (
              <li key={`${i}-${w}`}>{w}</li>
            ))}
          </ul>
        </Callout>
      ) : null}
      {authoredOptionA ? (
        <Callout
          variant={authoringPassed ? "info" : "warning"}
          title={
            authoringPassed
              ? "Authoring gate passed — zip and sandbox unlocked"
              : "LLM-authored module locked until the gate passes"
          }
          testId="option-a-authoring-gate"
        >
          <p className="text-sm">
            Completeness is not this bar. Zip download and sandbox install stay
            disabled until lint, policy (no invented taxes, no SSRF, no secrets),
            and a dry structural zip pass. Promote stays human.
          </p>
          {hostInstallOffers.length > 0 ? (
            <HostInstallPanel
              offers={hostInstallOffers}
              busy={aiBusy}
              disabled={aiBusy || isOdooOnline}
              disabledReason={
                isOdooOnline ? "Odoo Online cannot install Community apps from here" : undefined
              }
              onInstall={onInstallHost}
            />
          ) : null}
          {leftoverAuthoringFindings.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {leftoverAuthoringFindings.slice(0, 8).map((row, i) => (
                <li key={`auth-${i}`}>
                  {row.code ? `${row.code}: ` : ""}
                  {row.message}
                  {row.file ? ` (${row.file})` : ""}
                </li>
              ))}
            </ul>
          ) : null}
        </Callout>
      ) : null}
      {optionALines.length > 0 ? (
        <Callout
          variant={goLiveReady ? "info" : "warning"}
          title={
            goLiveReady
              ? "Option A sandbox proven — promote stays human"
              : capabilityPrimaryOptionA
                ? "Option A required — not a form-field pack"
                : "Option A surfaces in this draft"
          }
          testId="option-a-gaps"
        >
          <p className="text-sm">
            {capabilityPrimaryOptionA
              ? "This prompt needs a QWeb/PDF module (sandbox → promote). The draft zip scaffolds Pay now + QR. Live Apply only lands Char stubs — run Sandbox install & smoke to lift the scorecap."
              : "Some requested surfaces need an installable module. Live Apply still works for metadata; finish Option A separately."}
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {optionALines.slice(0, 8).map((line, i) => (
              <li key={`oa-${i}`}>{line}</li>
            ))}
          </ul>
          {capabilityPrimaryOptionA ? (
            <div className="mt-3 space-y-2">
              <Button
                type="button"
                size="sm"
                disabled={aiBusy || optionAProveBusy || zipLocked}
                data-testid="option-a-prove"
                title={
                  zipLocked ? "Authoring gate has not passed — sandbox stays locked" : undefined
                }
                onClick={onProveOptionA}
              >
                {optionAProveBusy ? "Sandbox smoke…" : "Sandbox install & smoke"}
              </Button>
              {optionAProveNote ? (
                <p className="text-xs text-muted" data-testid="option-a-prove-note">
                  {optionAProveNote}
                </p>
              ) : null}
            </div>
          ) : null}
        </Callout>
      ) : null}
      {computeSuggestions.length > 0 ? (
        <div className="space-y-2" data-testid="compute-suggestions">
          {computeSuggestions.map((s, i) => (
            <Callout key={`${s.model ?? "line"}-${i}`} variant="info" title="Line total suggestion">
              <p className="text-sm">{s.message}</p>
              <Link
                href={`/connections/${connectionId}/automations`}
                className="mt-2 inline-block text-sm text-accent underline"
              >
                Configure equation compute (advanced — confirm before apply)
              </Link>
            </Callout>
          ))}
        </div>
      ) : null}
      {refusals.length > 0 ? (
        <div className="space-y-2" data-testid="protected-refusals">
          {refusals.map((r, i) => (
            <Callout key={`${r.protected_module}-${i}`} variant="warning" title="Protected module">
              <p className="text-sm">
                <strong>{r.requested_capability}</strong>
              </p>
              <p className="mt-1 break-all font-mono text-sm text-muted">
                Model: {r.protected_module}
              </p>
              <p className="mt-1 text-sm">{r.reason || r.requested_capability}</p>
              <p className="mt-2 text-sm text-accent">{r.safe_alternative}</p>
            </Callout>
          ))}
        </div>
      ) : null}
    </div>
  );
}
