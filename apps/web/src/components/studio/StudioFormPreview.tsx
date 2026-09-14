"use client";

import type { PreviewFormView } from "@/lib/draft-form-preview";
import { normalizeFormPreview } from "@/lib/draft-form-preview";
import { OdooFormView, OdooPreviewScope } from "@/components/odoo-preview";

type StudioFormPreviewProps = {
  preview: PreviewFormView | Record<string, unknown>;
  flashFieldId?: string | null;
  highlightedFieldIds?: string[];
};

/**
 * Thin mobile/legacy wrapper around OdooFormView.
 * Prefer DraftOdooPreview (Form/List/Kanban switcher) for primary panes.
 */
export function StudioFormPreview({
  preview,
  flashFieldId,
  highlightedFieldIds = [],
}: StudioFormPreviewProps) {
  const view = normalizeFormPreview(preview);
  if (!view) return null;

  return (
    <OdooPreviewScope showBanner={false}>
      <OdooFormView
        view={view}
        flashFieldId={flashFieldId}
        highlightedFieldIds={highlightedFieldIds}
      />
    </OdooPreviewScope>
  );
}
