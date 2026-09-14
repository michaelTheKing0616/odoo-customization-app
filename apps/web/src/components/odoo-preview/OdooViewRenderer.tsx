"use client";

import type {
  PreviewFormView,
  PreviewKanbanView,
  PreviewListView,
  PreviewViewSchema,
} from "@/lib/draft-form-preview";
import { OdooFormView } from "./OdooFormView";
import { OdooKanbanView } from "./OdooKanbanView";
import { OdooListView } from "./OdooListView";

type OdooViewRendererProps = {
  schema: PreviewViewSchema;
  flashFieldId?: string | null;
  highlightedFieldIds?: string[];
};

export function OdooViewRenderer({
  schema,
  flashFieldId,
  highlightedFieldIds,
}: OdooViewRendererProps) {
  switch (schema.type) {
    case "form":
      return (
        <OdooFormView
          view={schema as PreviewFormView}
          flashFieldId={flashFieldId}
          highlightedFieldIds={highlightedFieldIds}
        />
      );
    case "list":
      return <OdooListView view={schema as PreviewListView} />;
    case "kanban":
      return <OdooKanbanView view={schema as PreviewKanbanView} />;
    default:
      return null;
  }
}
