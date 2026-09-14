"use client";

import type { PreviewFormView } from "@/lib/draft-form-preview";
import { OdooButtonBox } from "./OdooButtonBox";
import { OdooChatterStub } from "./OdooChatterStub";
import { OdooFieldGroup } from "./OdooFieldGroup";
import { OdooFormHeader } from "./OdooFormHeader";
import { OdooFormSheet } from "./OdooFormSheet";
import { OdooNotebook } from "./OdooNotebook";

type OdooFormViewProps = {
  view: PreviewFormView;
  flashFieldId?: string | null;
  highlightedFieldIds?: string[];
  showChatter?: boolean;
};

export function OdooFormView({
  view,
  flashFieldId,
  highlightedFieldIds = [],
  showChatter,
}: OdooFormViewProps) {
  const chatter =
    showChatter ?? (view.chatter !== "hidden" ? view.chatter === "stub" : false);
  const twoColumn = view.groupLayout === "two-column";

  return (
    <div className="odoo-form-canvas overflow-hidden shadow-sm" data-testid="odoo-form-view">
      <OdooFormHeader
        title={view.title}
        statusbar={view.statusbar}
        headerButtons={view.headerButtons}
      />
      <OdooFormSheet>
        <OdooButtonBox buttons={view.smartButtons || []} />
        <div
          className={`odoo-form-grid-2col ${twoColumn ? "is-two-column" : ""}`}
          data-testid="odoo-form-groups"
        >
          {view.groups.map((group) => (
            <OdooFieldGroup
              key={group.id}
              group={group}
              flashFieldId={flashFieldId}
              highlightedFieldIds={highlightedFieldIds}
            />
          ))}
        </div>
        {(view.notebooks || []).map((notebook) => (
          <OdooNotebook
            key={notebook.id}
            notebook={notebook}
            flashFieldId={flashFieldId}
            highlightedFieldIds={highlightedFieldIds}
          />
        ))}
        {chatter ? <OdooChatterStub density="full" /> : null}
      </OdooFormSheet>
    </div>
  );
}
