"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { PreviewFormView } from "@/lib/draft-form-preview";
import { readDesignerDraft } from "@/lib/view-designer-handoff";
import { StudioFormPreview } from "@/components/studio/StudioFormPreview";

/** View Designer opened from App Studio before install: show the generated view on the engine canvas, read-only. */
export function DesignerDraftHandoff({ connectionId, draftKey, model }: { connectionId: string; draftKey: string; model: string }) {
  const [view, setView] = useState<PreviewFormView | null | undefined>(undefined);
  useEffect(() => { setView(readDesignerDraft(draftKey)); }, [draftKey]);
  const live = `/connections/${encodeURIComponent(connectionId)}/view-designer?model=${encodeURIComponent(model)}&type=form`;
  if (view === undefined) return null;
  return (
    <div className="studio-preview-frame" data-testid="vd-draft-handoff">
      <p className="review-footer-note">
        {view
          ? "This screen comes from App Studio and isn't in Odoo yet. Install the app, then edit the real screen here."
          : "The App Studio draft for this screen is no longer here (it lives in this browser tab only)."}{" "}
        <Link href={live} data-testid="vd-draft-open-live">Open the installed screen</Link>
      </p>
      {view ? <StudioFormPreview preview={view} /> : null}
    </div>
  );
}
