"use client";

import Link from "next/link";
import type { FieldRow } from "@/lib/api";
import type { PreviewFormView, PreviewListView } from "@/lib/draft-form-preview";
import { OdooFormView, OdooListView, OdooPreviewScope } from "@/components/odoo-preview";

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
  if (!model || fields.length === 0) return null;

  const form = buildFormPreview(model, modelLabel, fields, enableMailThread);
  const list = buildListPreview(model, modelLabel, fields);

  return (
    <div className="mt-4 rounded border border-border-subtle bg-surface-muted/30 p-4" data-testid="builder-model-preview">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink">Layout preview</h3>
          <p className="text-xs text-muted">Read-only teaser from live fields — customize in View Designer.</p>
        </div>
        <Link
          href={`/connections/${connectionId}/designer?model=${encodeURIComponent(model)}`}
          className="text-sm font-medium text-accent hover:underline"
        >
          Customize layout in View Designer →
        </Link>
      </div>
      <OdooPreviewScope showBanner={false}>
        <OdooFormView view={form} />
        <div className="mt-4">
          <OdooListView view={list} />
        </div>
      </OdooPreviewScope>
    </div>
  );
}
