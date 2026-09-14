"use client";

import { DraftOdooPreview } from "@/components/odoo-preview";
import type { PreviewFormView } from "@/lib/draft-form-preview";

type StudioPreviewPaneProps = {
  draft: Record<string, unknown> | null | undefined;
  preview: PreviewFormView | null;
  breadcrumb: string;
  flashFieldId?: string | null;
  highlightedFieldIds?: string[];
  modelLabel?: string | null;
};

export function StudioPreviewPane({
  draft,
  preview,
  breadcrumb,
  flashFieldId,
  highlightedFieldIds,
  modelLabel,
}: StudioPreviewPaneProps) {
  if (!preview && !draft) {
    return (
      <p className="studio-preview-empty">
        No custom form in this draft. Describe what people should do in Odoo and try again.
      </p>
    );
  }

  return (
    <div className="studio-preview-frame" data-testid="draft-odoo-preview">
      {modelLabel ? (
        <p className="studio-preview-model">
          <span>Form</span>
          <code>{modelLabel}</code>
        </p>
      ) : null}
      <DraftOdooPreview
        draft={draft ?? null}
        breadcrumb={breadcrumb}
        formPreview={preview}
        flashFieldId={flashFieldId}
        highlightedFieldIds={highlightedFieldIds}
      />
    </div>
  );
}
