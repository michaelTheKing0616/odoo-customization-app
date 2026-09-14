"use client";

import { useEffect, useMemo, useState } from "react";
import type { PreviewFormView } from "@/lib/draft-form-preview";
import {
  isGoldOptionADraft,
  isOptionAAuthoredDraft,
  isRefuseCloneDraft,
  isStockReuseDraft,
  normalizeFormPreview,
  previewViewsFromDraft,
} from "@/lib/draft-form-preview";
import { isFieldPackDraft } from "@/lib/draft-models";
import {
  OdooControlPanel,
  OdooPreviewScope,
  OdooViewRenderer,
  type PreviewViewTab,
} from "@/components/odoo-preview";

type DraftOdooPreviewProps = {
  draft: Record<string, unknown> | null | undefined;
  breadcrumb?: string;
  flashFieldId?: string | null;
  highlightedFieldIds?: string[];
  /** Direct form preview override (when draft IR not yet stamped). */
  formPreview?: PreviewFormView | null;
};

export function DraftOdooPreview({
  draft,
  breadcrumb = "App Studio",
  flashFieldId,
  highlightedFieldIds = [],
  formPreview,
}: DraftOdooPreviewProps) {
  const views = useMemo(() => previewViewsFromDraft(draft), [draft]);
  const form = useMemo(
    () => normalizeFormPreview(formPreview) || views.form,
    [formPreview, views.form],
  );
  const availableViews = useMemo(() => {
    const tabs: PreviewViewTab[] = [];
    if (form) tabs.push("form");
    if (views.list) tabs.push("list");
    if (views.kanban) tabs.push("kanban");
    return tabs.length ? tabs : (["form"] as PreviewViewTab[]);
  }, [form, views.kanban, views.list]);

  const [activeView, setActiveView] = useState<PreviewViewTab>("form");

  useEffect(() => {
    if (!availableViews.includes(activeView)) {
      setActiveView(availableViews[0] || "form");
    }
  }, [activeView, availableViews]);

  const schema =
    activeView === "list" && views.list
      ? views.list
      : activeView === "kanban" && views.kanban
        ? views.kanban
        : form;

  if (!schema) {
    const emptyReason = isStockReuseDraft(draft)
      ? "No custom form — this draft uses stock Community apps only. Job Autopilot is the next step, not a new x_* sheet."
      : isRefuseCloneDraft(draft)
        ? "This prompt was refused (Apps Store clone). Describe the residual process instead."
        : isGoldOptionADraft(draft)
          ? "No new x_* app. This is an Option A module (Python + cron) — download the zip and sandbox-prove. Live Install will not fetch CBN rates."
        : isOptionAAuthoredDraft(draft)
          ? "This is an Option A module on a stock form (for example Sales markup). Live Install will not land Python. Download zip → sandbox prove → Promote after the authoring gate passes."
        : isFieldPackDraft(draft)
          ? "This should preview the extra fields on a form people already use (for example vendor bills). Generate again if the canvas is empty."
        : "No custom form in this draft. Start a new app if you expected a new kind of record.";
    return (
      <p
        data-testid="draft-odoo-preview-empty"
        style={{ color: "var(--text-secondary)", fontSize: "var(--font-size-sm)" }}
      >
        {emptyReason}
      </p>
    );
  }

  return (
    <OdooPreviewScope>
      <OdooControlPanel
        breadcrumb={`${breadcrumb} › ${form?.title || "Preview"}`}
        activeView={activeView}
        availableViews={availableViews}
        onViewChange={setActiveView}
      />
      <div data-testid="draft-odoo-preview-body" data-active-view={activeView}>
        <OdooViewRenderer
          schema={schema}
          flashFieldId={flashFieldId}
          highlightedFieldIds={highlightedFieldIds}
        />
      </div>
    </OdooPreviewScope>
  );
}
