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

function ContactTitleArea() {
  return (
    <div className="odoo-contact-title" data-testid="odoo-contact-title">
      <div className="odoo-contact-avatar" aria-hidden>
        <span>👤</span>
      </div>
      <div className="odoo-contact-title-text">
        <div className="odoo-contact-name">Sample contact</div>
        <div className="odoo-contact-subtitle">Contact</div>
      </div>
    </div>
  );
}

export function OdooFormView({
  view,
  flashFieldId,
  highlightedFieldIds = [],
  showChatter,
}: OdooFormViewProps) {
  const chatter =
    showChatter ?? (view.chatter !== "hidden" ? view.chatter === "stub" : false);
  const twoColumn = view.groupLayout === "two-column";
  const showContactChrome =
    view.model === "res.partner" ||
    (view.groups || []).some((g) => g.id === "host_identity");

  return (
    <div className="odoo-form-canvas overflow-hidden shadow-sm" data-testid="odoo-form-view">
      <OdooFormHeader
        title={view.title}
        statusbar={view.statusbar}
        headerButtons={view.headerButtons}
      />
      <OdooFormSheet>
        {showContactChrome ? <ContactTitleArea /> : null}
        {(view.alerts || []).map((alert) => (
          <div
            key={alert.id}
            className={`odoo-form-alert odoo-form-alert--${alert.level || "warning"}`}
            role="alert"
            data-testid={`odoo-form-alert-${alert.id}`}
            data-hint-kind={alert.kind || "alert"}
          >
            {/* One banner line — never title + redundant When: echo */}
            <div className="odoo-form-alert-message">{alert.message}</div>
          </div>
        ))}
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
