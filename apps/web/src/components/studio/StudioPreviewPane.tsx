"use client";

import { DraftOdooPreview } from "@/components/odoo-preview";
import type { PreviewFormView } from "@/lib/draft-form-preview";
import type { IntegrationPlan } from "@/lib/integration-plan";
import { deferredIntegrationsOf } from "@/lib/integration-plan";
import { StudioIntegrationPlanNote } from "./StudioIntegrationPlanNote";

type StudioPreviewPaneProps = {
  draft: Record<string, unknown> | null | undefined;
  preview: PreviewFormView | null;
  breadcrumb: string;
  flashFieldId?: string | null;
  highlightedFieldIds?: string[];
  /** @deprecated Technical model chrome removed from operator Review. */
  modelLabel?: string | null;
  /** Optional-integration plan; shown as one quiet note above the form. */
  integrationPlan?: IntegrationPlan | null;
};

export function StudioPreviewPane({
  draft,
  preview,
  breadcrumb,
  flashFieldId,
  highlightedFieldIds,
  integrationPlan = null,
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
      <StudioIntegrationPlanNote plan={integrationPlan} />
      <DraftOdooPreview
        draft={draft ?? null}
        breadcrumb={breadcrumb}
        formPreview={preview}
        flashFieldId={flashFieldId}
        highlightedFieldIds={highlightedFieldIds}
        deferredIntegrations={deferredIntegrationsOf(integrationPlan)}
        omittedModels={integrationPlan?.omitted_models}
      />
    </div>
  );
}
