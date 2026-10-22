"use client";

import { useState } from "react";
import type { PreviewNotebook } from "@/lib/draft-form-preview";
import { OdooField } from "./OdooField";

type OdooNotebookProps = {
  notebook: PreviewNotebook;
  flashFieldId?: string | null;
  highlightedFieldIds?: string[];
};

export function OdooNotebook({ notebook, flashFieldId, highlightedFieldIds = [] }: OdooNotebookProps) {
  const [activePageId, setActivePageId] = useState(notebook.pages[0]?.id || "");
  const activePage = notebook.pages.find((page) => page.id === activePageId) || notebook.pages[0];
  if (notebook.pages.length === 0) return null;
  return (
    <div className="ofp-notebook" data-testid={`odoo-notebook-${notebook.id}`}>
      <div className="ofp-tabs" role="tablist">
        {notebook.pages.map((page) => {
          const selected = page.id === activePage?.id;
          return (
            <button
              key={page.id}
              type="button"
              role="tab"
              aria-selected={selected}
              className={`ofp-tab ${selected ? "is-active" : ""}`}
              onClick={() => setActivePageId(page.id)}
            >
              {page.string}
            </button>
          );
        })}
      </div>
      {activePage ? (
        <div key={activePage.id} className="ofp-tab-panel" role="tabpanel">
          {activePage.fields.map((field) => (
            <OdooField
              key={field.id}
              field={field}
              highlighted={flashFieldId === field.id || highlightedFieldIds.includes(field.id)}
            />
          ))}
          {activePage.fields.length === 0 ? <p className="ofp-empty">Nothing on this tab yet</p> : null}
        </div>
      ) : null}
    </div>
  );
}
