"use client";

import type { PreviewField, PreviewFormView, PreviewGroup } from "@/lib/draft-form-preview";
import { OdooButtonBox } from "./OdooButtonBox";
import { OdooChatterStub } from "./OdooChatterStub";
import { OdooFieldGroup } from "./OdooFieldGroup";
import { OdooFormHeader } from "./OdooFormHeader";
import { OdooFormSheet } from "./OdooFormSheet";
import { OdooNotebook } from "./OdooNotebook";

/** An app the plan left out or deferred, shown as a marked ghost row on the sheet. */
export type PreviewDeferredIntegration = {
  label: string;
  status: "left_out" | "deferred";
  note?: string;
};

type OdooFormViewProps = {
  view: PreviewFormView;
  flashFieldId?: string | null;
  highlightedFieldIds?: string[];
  showChatter?: boolean;
  deferredIntegrations?: PreviewDeferredIntegration[];
};

const TITLE_NAMES = ["x_name", "name", "_host_name", "display_name"];

/** The record name field shown big in oe_title (char only), or null. */
export function titleFieldOf(view: PreviewFormView): PreviewField | null {
  const all = (view.groups || []).flatMap((g) => g.fields || []);
  const wanted = view.recordTitleField ? [view.recordTitleField, ...TITLE_NAMES] : TITLE_NAMES;
  for (const name of wanted) {
    const hit = all.find((f) => f.name === name);
    if (hit && (!hit.ttype || hit.ttype === "char")) return hit;
  }
  return null;
}

/** Odoo puts inner groups side by side; split one long group into two columns. */
function layoutGroups(groups: PreviewGroup[], twoColumn: boolean): { groups: PreviewGroup[]; columns: 1 | 2 } {
  if (groups.length === 1 && groups[0].columns === 2 && groups[0].fields.length > 3) {
    const g = groups[0];
    const inline = g.fields.filter((f) => !["one2many", "html"].includes((f.ttype || "").toLowerCase()));
    const wide = g.fields.filter((f) => ["one2many", "html"].includes((f.ttype || "").toLowerCase()));
    const half = Math.ceil(inline.length / 2);
    return {
      columns: 2,
      groups: [
        { ...g, id: g.id, fields: inline.slice(0, half) },
        { ...g, id: `${g.id}__col2`, string: "", fields: inline.slice(half) },
        ...(wide.length ? [{ ...g, id: `${g.id}__wide`, string: "", columns: 1 as const, fields: wide }] : []),
      ],
    };
  }
  return { groups, columns: twoColumn || groups.length > 1 ? 2 : 1 };
}

function placeholderFor(field: PreviewField): string {
  const label = (field.string || "Name").trim();
  return `e.g. ${label}`;
}

export function OdooFormView({
  view,
  flashFieldId,
  highlightedFieldIds = [],
  showChatter,
  deferredIntegrations = [],
}: OdooFormViewProps) {
  const chatter = showChatter ?? (view.chatter !== "hidden" ? view.chatter === "stub" : false);
  const isContact =
    view.model === "res.partner" || (view.groups || []).some((g) => g.id === "host_identity");
  const titleField = titleFieldOf(view);
  const groupsWithoutTitle = (view.groups || [])
    .map((g) => ({ ...g, fields: g.fields.filter((f) => f !== titleField) }))
    .filter((g) => g.fields.length > 0 || (view.groups || []).length === 1);
  const laid = layoutGroups(groupsWithoutTitle, view.groupLayout === "two-column");
  const titleHighlighted =
    titleField != null &&
    (flashFieldId === titleField.id || highlightedFieldIds.includes(titleField.id));
  const titleText =
    titleField == null
      ? ""
      : titleField.name === "_host_name"
        ? "Sample contact"
        : "";

  return (
    <div className="ofp" data-testid="odoo-form-view" data-chatter={chatter ? "on" : "off"}>
      <div className="ofp-body">
        <div className="ofp-main">
          <OdooFormHeader
            title={view.title}
            statusbar={view.statusbar}
            headerButtons={view.headerButtons}
            humanizeStages
          />
          <OdooFormSheet>
            {(view.alerts || []).map((alert) => (
              <div
                key={alert.id}
                className={`ofp-alert ofp-alert--${alert.level || "warning"}`}
                role="alert"
                data-testid={`odoo-form-alert-${alert.id}`}
                data-hint-kind={alert.kind || "alert"}
              >
                <div className="ofp-alert-message">{alert.message}</div>
              </div>
            ))}
            <OdooButtonBox buttons={view.smartButtons || []} />
            <div className={`ofp-title ${isContact ? "has-avatar" : ""}`} data-testid="odoo-form-title">
              <div className="ofp-title-main">
                {titleField ? (
                  <>
                    <label className="ofp-title-label">
                      {titleField.string || "Name"}
                      {titleField.required ? <span className="ofp-required" aria-hidden>*</span> : null}
                    </label>
                    <h1
                      className={`ofp-title-input ${titleField.required ? "is-required" : ""} ${titleHighlighted ? "field-highlight" : ""}`}
                      data-testid={`odoo-field-${titleField.name}`}
                    >
                      <span
                        className={titleText ? "ofp-title-value" : "ofp-title-placeholder"}
                        data-testid={`odoo-widget-char-${titleField.name}`}
                      >
                        {titleText || placeholderFor(titleField)}
                      </span>
                    </h1>
                  </>
                ) : (
                  <h1 className="ofp-title-input ofp-title-static">{view.title}</h1>
                )}
              </div>
              {isContact ? (
                <div className="ofp-avatar-box" data-testid="odoo-contact-title" aria-hidden>
                  <span>Photo</span>
                </div>
              ) : null}
            </div>
            <div
              className={`ofp-groups ${laid.columns === 2 ? "is-two-column" : ""}`}
              data-testid="odoo-form-groups"
            >
              {laid.groups.map((group) => (
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
            {deferredIntegrations.length > 0 ? (
              <section className="ofp-deferred" data-testid="odoo-form-deferred">
                <div className="ofp-group-title">Not in this build</div>
                {deferredIntegrations.map((item) => (
                  <div key={item.label} className="ofp-field is-deferred" title={item.note || undefined}>
                    <div className="ofp-label">
                      <span className="ofp-label-text">{item.label}</span>
                    </div>
                    <div className="ofp-value">
                      <span className="ofp-input ofp-ghost" />
                      <span className="ofp-deferred-badge" data-status={item.status}>
                        {item.status === "left_out" ? "Left out" : "Install later"}
                      </span>
                    </div>
                  </div>
                ))}
              </section>
            ) : null}
          </OdooFormSheet>
        </div>
        {chatter ? <OdooChatterStub density="full" /> : null}
      </div>
    </div>
  );
}
