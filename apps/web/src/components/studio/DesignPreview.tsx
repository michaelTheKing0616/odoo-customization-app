"use client";

import { useMemo, useState } from "react";
import { DraftOdooPreview } from "@/components/odoo-preview";
import { designPreviews } from "@/lib/design-preview";
import { designerDraftHref, stashDesignerDraft } from "@/lib/view-designer-handoff";
import type { StudioAppDesign } from "@/lib/studio-session";

/** The design (agent or pipeline) as an Odoo-like screen, one tab per form, with a hand-off to View Designer. */
export function DesignPreview({ design, connectionId }: { design: StudioAppDesign; connectionId?: string }) {
  const views = useMemo(() => designPreviews(design), [design]);
  const [i, setI] = useState(0);
  if (!views.length) return null;
  const view = views[Math.min(i, views.length - 1)];
  const open = () => {
    if (!connectionId) return;
    window.location.assign(designerDraftHref(connectionId, view.model, stashDesignerDraft(view)));
  };
  return (
    <section className="diagnosis-field" data-testid="studio-design-preview" aria-label="Preview of the design">
      <div className="app-design-preview-bar">
        {views.length > 1 ? (
          <div role="tablist" aria-label="Screens in this design">
            {views.map((v, n) => (
              <button key={v.model} type="button" role="tab" aria-selected={n === i}
                className={n === i ? "btn btn-secondary is-active" : "btn btn-ghost"} onClick={() => setI(n)}>
                {v.title}
              </button>
            ))}
          </div>
        ) : null}
        {connectionId ? (
          <button type="button" className="btn btn-secondary" data-testid="design-open-view-designer" onClick={open}>
            Open in View Designer
          </button>
        ) : null}
      </div>
      <DraftOdooPreview draft={null} formPreview={view} breadcrumb={design.app_name || "App Studio"} />
    </section>
  );
}
