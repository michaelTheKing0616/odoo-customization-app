"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { Callout } from "@/components/ui/Callout";
import { IconAutomations, IconViews } from "@/components/ui/icons";
import { ModelTierInline } from "@/components/ModelTierInline";
import { BuilderModelPreview } from "@/components/builder/BuilderModelPreview";
import { FieldList } from "@/components/builder/FieldList";
import { automationsHref, isCustomTechnicalName, viewDesignerHref } from "@/lib/builderForm";
import type { FieldRow, ModelRow } from "@/lib/api";

type ModelDetailProps = {
  connectionId: string;
  model: string;
  modelLabel: string;
  customRow: ModelRow | null;
  fields: FieldRow[];
  fieldsLoading?: boolean;
  fieldQuery: string;
  selectedFieldId: number | null;
  justCreated?: boolean;
  enableMailThread?: boolean;
  busy?: boolean;
  onFieldQueryChange: (query: string) => void;
  onSelectField: (row: FieldRow) => void;
  onNewField: () => void;
  onRemoveField: (row: FieldRow) => void;
  onDeleteModel?: () => void;
};

export function ModelDetail({
  connectionId,
  model,
  modelLabel,
  customRow,
  fields,
  fieldsLoading,
  fieldQuery,
  selectedFieldId,
  justCreated,
  enableMailThread,
  busy,
  onFieldQueryChange,
  onSelectField,
  onNewField,
  onRemoveField,
  onDeleteModel,
}: ModelDetailProps) {
  const designer = viewDesignerHref(connectionId, model);
  const automations = automationsHref(connectionId, model);
  const custom = isCustomTechnicalName(model);

  return (
    <div className="space-y-4" data-testid="builder-model-detail">
      {justCreated ? (
        <Callout
          variant="info"
          title="Model ready"
          testId="builder-model-success"
          actions={
            <Button variant="primary" size="sm" asChild>
              <Link href={designer} data-testid="builder-success-designer">
                Customize layout in View Designer
              </Link>
            </Button>
          }
        >
          Default list, form, and search views are in place. Add fields here, or jump to View
          Designer to arrange the layout.
        </Callout>
      ) : null}

      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
              {custom ? "Custom model" : "Existing model"}
            </p>
            <h2 className="text-base font-semibold text-ink">{modelLabel || model}</h2>
            <p className="mt-0.5 font-mono text-[11px] text-muted">{model}</p>
            <div className="mt-2">
              <ModelTierInline connectionId={connectionId} model={model} />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" asChild>
              <Link href={designer} data-testid="builder-designer-link">
                <IconViews className="h-3.5 w-3.5" aria-hidden />
                View Designer
              </Link>
            </Button>
            <Button variant="secondary" size="sm" asChild>
              <Link href={automations} data-testid="builder-automations-link">
                <IconAutomations className="h-3.5 w-3.5" aria-hidden />
                Automations
              </Link>
            </Button>
          </div>
        </div>
        {custom && onDeleteModel ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-danger"
            disabled={busy}
            onClick={onDeleteModel}
            data-testid="builder-delete-model"
          >
            Delete model
          </Button>
        ) : null}
      </Card>

      <FieldList
        fields={fields}
        loading={fieldsLoading}
        selectedFieldId={selectedFieldId}
        query={fieldQuery}
        onQueryChange={onFieldQueryChange}
        onSelect={onSelectField}
        onCreate={onNewField}
        onRemoveFromModel={onRemoveField}
        designerHref={designer}
      />

      <BuilderModelPreview
        connectionId={connectionId}
        model={model}
        modelLabel={modelLabel || customRow?.name || model}
        fields={fields}
        enableMailThread={enableMailThread}
      />
    </div>
  );
}
