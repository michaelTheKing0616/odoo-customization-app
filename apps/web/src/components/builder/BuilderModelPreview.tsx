"use client";

import Link from "next/link";
import type { FieldRow } from "@/lib/api";
import type { PreviewFormView, PreviewListView } from "@/lib/draft-form-preview";
import { OdooFormView, OdooListView, OdooPreviewScope } from "@/components/odoo-preview";
import { Button } from "@/components/ui/Button";
import { Card, EmptyState } from "@/components/ui/layout-primitives";
import { Tabs } from "@/components/ui/Tabs";
import { IconViews } from "@/components/ui/icons";
import { automationsHref, viewDesignerHref } from "@/lib/builderForm";

type BuilderModelPreviewProps = {
  connectionId: string;
  model: string;
  modelLabel: string;
  fields: FieldRow[];
  enableMailThread?: boolean;
};

function buildFormPreview(
  model: string,
  modelLabel: string,
  fields: FieldRow[],
  enableMailThread?: boolean,
): PreviewFormView {
  const previewFields = fields.slice(0, 12).map((f) => ({
    id: f.name,
    name: f.name,
    string: f.field_description || f.name,
    ttype: f.ttype,
  }));
  return {
    type: "form",
    model,
    title: modelLabel || model,
    groups: [
      {
        id: "identity",
        string: "Identity",
        columns: 1,
        fields: previewFields,
      },
    ],
    chatter: enableMailThread ? "stub" : "hidden",
    groupLayout: "stack",
    smartButtons: [],
    headerButtons: [],
  };
}

function buildListPreview(model: string, modelLabel: string, fields: FieldRow[]): PreviewListView {
  const columns = fields.slice(0, 6).map((f) => ({
    id: f.name,
    name: f.name,
    string: f.field_description || f.name,
  }));
  return {
    type: "list",
    model,
    title: modelLabel || model,
    columns,
  };
}

export function BuilderModelPreview({
  connectionId,
  model,
  modelLabel,
  fields,
  enableMailThread,
}: BuilderModelPreviewProps) {
  if (!model) return null;

  const designer = viewDesignerHref(connectionId, model);
  const automations = automationsHref(connectionId, model);

  if (fields.length === 0) {
    return (
      <Card className="p-4" data-testid="builder-model-preview">
        <EmptyState
          icon={<IconViews className="h-5 w-5" />}
          title="Layout preview waits on fields"
          description="Add a field to see a form and list teaser. Default views already exist on new x_ models."
          action={
            <Button variant="secondary" size="sm" asChild>
              <Link href={designer}>Open View Designer</Link>
            </Button>
          }
        />
      </Card>
    );
  }

  const form = buildFormPreview(model, modelLabel, fields, enableMailThread);
  const list = buildListPreview(model, modelLabel, fields);

  return (
    <Card className="space-y-4 p-5" data-testid="builder-model-preview">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">Preview</p>
          <h3 className="text-sm font-semibold text-ink">Layout teaser</h3>
          <p className="mt-1 text-xs text-muted">
            Read-only from live fields — not the saved arch. View Designer is the source of truth
            for layout.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" asChild>
            <Link href={designer}>Customize layout in View Designer</Link>
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <Link href={automations}>Automations for this model</Link>
          </Button>
        </div>
      </div>
      <OdooPreviewScope showBanner={false}>
        <Tabs
          defaultValue="form"
          items={[
            { value: "form", label: "Form", content: <OdooFormView view={form} /> },
            { value: "list", label: "List", content: <OdooListView view={list} /> },
          ]}
        />
      </OdooPreviewScope>
    </Card>
  );
}
