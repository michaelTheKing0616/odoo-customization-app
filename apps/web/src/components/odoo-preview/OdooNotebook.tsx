"use client";

import { useState } from "react";
import type { PreviewNotebook } from "@/lib/draft-form-preview";
import { OdooField } from "./OdooField";

type OdooNotebookProps = {
  notebook: PreviewNotebook;
  flashFieldId?: string | null;
  highlightedFieldIds?: string[];
};

export function OdooNotebook({
  notebook,
  flashFieldId,
  highlightedFieldIds = [],
}: OdooNotebookProps) {
  const [activePageId, setActivePageId] = useState(notebook.pages[0]?.id || "");
  const activePage =
    notebook.pages.find((page) => page.id === activePageId) || notebook.pages[0];

  if (notebook.pages.length === 0) return null;

  return (
    <div className="mt-4 border border-[var(--odoo-border)]" data-testid={`odoo-notebook-${notebook.id}`}>
      <div className="flex flex-wrap border-b border-[var(--odoo-border)] bg-[color-mix(in_srgb,var(--odoo-canvas)_50%,var(--surface))]">
        {notebook.pages.map((page) => (
          <button
            key={page.id}
            type="button"
            className={`border-r border-[var(--odoo-border)] px-3 py-1.5 text-xs font-semibold ${
              page.id === activePage?.id
                ? "bg-surface text-[var(--odoo-primary)]"
                : "text-[var(--odoo-muted)]"
            }`}
            onClick={() => setActivePageId(page.id)}
          >
            {page.string}
          </button>
        ))}
      </div>
      {activePage ? (
        <div className="p-2">
          {activePage.fields.map((field) => (
            <OdooField
              key={field.id}
              field={field}
              highlighted={
                flashFieldId === field.id || highlightedFieldIds.includes(field.id)
              }
            />
          ))}
          {activePage.fields.length === 0 ? (
            <p className="text-xs text-[var(--odoo-muted)]">No fields on this tab</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
