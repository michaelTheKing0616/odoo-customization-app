"use client";

import type { PreviewGroup } from "@/lib/draft-form-preview";
import { OdooField } from "./OdooField";

type OdooFieldGroupProps = {
  group: PreviewGroup;
  flashFieldId?: string | null;
  highlightedFieldIds?: string[];
  onFieldClick?: (fieldId: string) => void;
};

export function OdooFieldGroup({
  group,
  flashFieldId,
  highlightedFieldIds = [],
  onFieldClick,
}: OdooFieldGroupProps) {
  // Odoo shows no caption for an untitled group; hide generic placeholders.
  const raw = (group.string || "").trim();
  const title = /^group$/i.test(raw) ? "" : raw;
  return (
    <section className="ofp-group" data-testid={`odoo-group-${group.id}`}>
      {title ? <div className="ofp-group-title">{title}</div> : null}
      <div className="ofp-group-body">
        {group.fields.map((field) => (
          <OdooField
            key={field.id}
            field={field}
            highlighted={flashFieldId === field.id || highlightedFieldIds.includes(field.id)}
            onClick={onFieldClick ? () => onFieldClick(field.id) : undefined}
          />
        ))}
        {group.fields.length === 0 ? <p className="ofp-empty">No fields yet</p> : null}
      </div>
    </section>
  );
}
