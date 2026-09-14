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
  return (
    <section className="odoo-field-group" data-testid={`odoo-group-${group.id}`}>
      <div className="odoo-field-group-title">{group.string || "Group"}</div>
      <div className="space-y-0">
        {group.fields.map((field) => (
          <OdooField
            key={field.id}
            field={field}
            highlighted={
              flashFieldId === field.id || highlightedFieldIds.includes(field.id)
            }
            onClick={onFieldClick ? () => onFieldClick(field.id) : undefined}
          />
        ))}
        {group.fields.length === 0 ? (
          <p className="text-xs text-[var(--odoo-muted)]">No fields</p>
        ) : null}
      </div>
    </section>
  );
}
