"use client";

import { AskWhyButton } from "@/components/expert/AskWhyButton";
import { SaveAsComponentButton } from "@/components/SaveAsComponentButton";
import { SuggestTemplateButton } from "@/components/SuggestTemplateButton";
import { StudioPreviewPane } from "@/components/studio/StudioPreviewPane";
import { Callout } from "@/components/ui/Callout";
import { CodeBlock } from "@/components/ui/CodeBlock";
import type { OptionASettings, PreviewFormView, StockAppRow } from "@/lib/draft-form-preview";

type DraftStudioPreviewPaneProps = {
  connectionId: string;
  draft: Record<string, unknown>;
  preview: PreviewFormView | null;
  optionASettings: OptionASettings | null;
  stockReuse: boolean;
  stockApps: StockAppRow[];
  nlPrompt: string;
};

export function DraftStudioPreviewPane({
  connectionId,
  draft,
  preview,
  optionASettings,
  stockReuse,
  stockApps,
  nlPrompt,
}: DraftStudioPreviewPaneProps) {
  const models = Array.isArray(draft.models)
    ? (draft.models as Array<{ model?: string; description?: string }>)
    : [];
  const grain = typeof draft.grain === "string" ? draft.grain : "";
  const connect = draft.connect_points as
    | { host_label?: string; host_model?: string }
    | undefined;
  const isComponent = Boolean(draft._component) || (grain && grain !== "full_app");

  return (
    <div className="studio-preview-frame">
      <div data-testid="stage-h-form-preview">
        <StudioPreviewPane
          draft={draft}
          preview={preview}
          breadcrumb="Draft Studio"
          modelLabel={preview?.model || null}
        />
      </div>
      {optionASettings ? (
        <Callout
          variant="info"
          title={`Option A settings · ${optionASettings.model}`}
          testId="option-a-settings-pane"
        >
          <p className="text-sm text-muted">
            These toggles inherit stock POS / document hosts. This is not a live
            thermal studio and not an x_receipt app.
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {optionASettings.fields.map((f) => (
              <li key={f.name}>
                <span className="font-mono text-xs">{f.name}</span>
                {f.string ? ` — ${f.string}` : ""}
                {f.help ? <span className="text-muted"> ({f.help})</span> : null}
              </li>
            ))}
          </ul>
        </Callout>
      ) : null}
      {isComponent ? (
        <p className="text-sm text-ink">
          Extends{" "}
          <span className="font-medium">
            {String(connect?.host_label || connect?.host_model || "a stock app")}
          </span>
          <span className="text-muted">
            {" "}
            ({String(connect?.host_model || "?")}) — custom models only if the prompt asked
            for a register or checklist. Nothing writes to Odoo until Apply.
          </span>
        </p>
      ) : stockReuse ? (
        <p className="text-sm text-ink" data-testid="stock-reuse-surface">
          {stockApps.length ? stockApps.map((app) => app.label).join(" · ") : "Named Community apps"}{" "}
          — no custom models, views, or smart buttons. Use Job Autopilot.
        </p>
      ) : (
        <p className="text-xs text-muted">
          {models.length || "?"} models · {Array.isArray(draft.views) ? draft.views.length : 0}{" "}
          views ·{" "}
          {Array.isArray(draft.smart_buttons) ? draft.smart_buttons.length : 0} smart buttons
          {typeof draft.domain_pack === "string" ? ` · pack: ${draft.domain_pack}` : ""}
        </p>
      )}
      {models.length > 0 ? (
        <ul className="space-y-1 text-sm" data-testid="draft-model-review">
          {models.map((m) => (
            <li key={String(m.model)} className="flex items-center gap-2">
              <span className="font-mono text-muted">{m.model}</span>
              <AskWhyButton
                subject={String(m.model)}
                context={`Draft model ${m.model}${m.description ? `: ${m.description}` : ""}`}
                connectionId={connectionId}
                draft={draft}
                userPrompt={nlPrompt.trim()}
              />
            </li>
          ))}
        </ul>
      ) : null}
      <details className="draft-studio-disclosure">
        <summary className="cursor-pointer text-xs font-medium text-muted">
          ModuleSpec JSON
        </summary>
        <CodeBlock className="mt-2" language="json" code={JSON.stringify(draft, null, 2)} />
      </details>
      <div className="flex flex-wrap gap-2">
        <SuggestTemplateButton spec={draft} connectionId={connectionId} />
        {isComponent ? <SaveAsComponentButton spec={draft} /> : null}
      </div>
    </div>
  );
}
