"use client";

import { useMemo } from "react";
import type { PreviewFormView } from "@/lib/draft-form-preview";
import { normalizeFormPreview } from "@/lib/draft-form-preview";
import { indexTree } from "@/lib/viewEngineOps";
import { EngineCanvas } from "@/components/view-designer/EngineCanvas";
import { draftToEngine } from "@/components/view-designer/draftEngine";
import vd from "@/components/view-designer/ViewDesigner.module.css";

type StudioFormPreviewProps = {
  preview: PreviewFormView | Record<string, unknown>;
  flashFieldId?: string | null;
  highlightedFieldIds?: string[];
};

const noop = () => undefined;

/**
 * Draft-mode render through the shared view engine (SPEC stage 4): the same canvas as View Designer,
 * read-only, with sample values that are labelled. Odoo's own render is the reference after install.
 */
export function StudioFormPreview({ preview, flashFieldId, highlightedFieldIds = [] }: StudioFormPreviewProps) {
  const view = normalizeFormPreview(preview);
  const built = useMemo(() => (view ? draftToEngine(view) : null), [view]);
  const index = useMemo(() => (built ? indexTree(built.tree) : null), [built]);
  if (!view || !built || !index) return null;
  const marks = Object.fromEntries(
    [...highlightedFieldIds, ...(flashFieldId ? [flashFieldId] : [])].map((id) => [`draft:field:${id}`, "changed" as const]),
  );
  return (
    <div data-testid="studio-engine-preview" data-mode="draft">
      <p className={vd.row}>
        <span className={vd.sampleBadge}>Sample values, not real records</span>
      </p>
      <EngineCanvas
        tree={built.tree}
        index={index}
        record={built.record}
        selectedId={null}
        onSelect={noop}
        onMove={noop}
        onInsertField={noop}
        markers={marks}
        readOnly
      />
    </div>
  );
}
