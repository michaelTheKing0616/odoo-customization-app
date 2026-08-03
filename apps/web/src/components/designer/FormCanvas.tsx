"use client";

import { useEffect } from "react";

/**
 * Odoo-familiar form canvas chrome for the View Designer.
 * Structural preview — Open-in-Odoo remains authoritative.
 */

export type CanvasField = {
  id: string;
  name: string;
  string?: string;
};

export type CanvasGroup = {
  id: string;
  string?: string;
  fields: CanvasField[];
};

export type CanvasPage = {
  id: string;
  string: string;
  fields: CanvasField[];
};

export type CanvasNotebook = {
  id: string;
  pages: CanvasPage[];
};

export type CanvasSmartButton = {
  id: string;
  string: string;
};

export type FormCanvasProps = {
  title: string;
  statusbar?: string | null;
  headerButtons?: string[];
  smartButtons?: CanvasSmartButton[];
  groups: CanvasGroup[];
  notebooks?: CanvasNotebook[];
  flashId?: string | null;
  selectedFieldId?: string | null;
  onSelectField?: (fieldId: string) => void;
  onMoveField?: (fieldId: string, dir: -1 | 1) => void;
  onDropFieldName?: (groupId: string, fieldName: string) => void;
  onDropFieldOnPage?: (notebookId: string, pageId: string, fieldName: string) => void;
};

export function FormCanvas({
  title,
  statusbar,
  headerButtons = [],
  smartButtons = [],
  groups,
  notebooks = [],
  flashId = null,
  selectedFieldId,
  onSelectField,
  onMoveField,
  onDropFieldName,
  onDropFieldOnPage,
}: FormCanvasProps) {
  useEffect(() => {
    if (!selectedFieldId || !onMoveField) return;
    const move = onMoveField;
    const fieldId = selectedFieldId;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return;
      }
      e.preventDefault();
      move(fieldId, e.key === "ArrowUp" ? -1 : 1);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedFieldId, onMoveField]);

  return (
    <div
      className="odoo-form-canvas overflow-hidden shadow-sm"
      data-testid="form-canvas"
      tabIndex={0}
    >
      <div className="odoo-form-header flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-[var(--odoo-primary)]">{title}</span>
        {statusbar && (
          <span className="rounded bg-[var(--odoo-primary)] px-2 py-0.5 text-xs text-white">
            statusbar · {statusbar}
          </span>
        )}
        {headerButtons.map((b) => (
          <span
            key={b}
            className="rounded border border-[var(--odoo-border)] bg-white px-2 py-0.5 text-xs"
          >
            {b}
          </span>
        ))}
      </div>
      <div className="p-3">
        {smartButtons.length > 0 && (
          <div className="odoo-button-box">
            {smartButtons.map((b) => (
              <div key={b.id} className="odoo-stat-button">
                {b.string}
              </div>
            ))}
          </div>
        )}
        <div className="space-y-3">
          {groups.map((g) => (
            <div
              key={g.id}
              data-canvas-id={g.id}
              className={`border border-[var(--odoo-border)] bg-white p-2 transition ring-offset-2 ${
                flashId === g.id ? "ring-2 ring-[var(--odoo-primary)]" : ""
              }`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const name = e.dataTransfer.getData("text/odoo-field");
                if (name && onDropFieldName) onDropFieldName(g.id, name);
              }}
            >
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--odoo-muted)]">
                {g.string || "Group"}
              </div>
              <ul className="space-y-1">
                {g.fields.map((f, idx) => (
                  <li
                    key={f.id}
                    className={`flex items-center justify-between gap-2 border px-2 py-1 text-sm ${
                      selectedFieldId === f.id
                        ? "border-[var(--odoo-primary)] bg-[#f5eef3]"
                        : "border-[var(--odoo-border)]"
                    }`}
                  >
                    <button
                      type="button"
                      className="flex-1 text-left text-xs"
                      onClick={() => onSelectField?.(f.id)}
                    >
                      <span className="font-sans font-medium text-[var(--odoo-text,#1a1a1a)]">
                        {f.string || f.name}
                      </span>
                      <span className="ml-2 font-mono text-[var(--odoo-muted)]">{f.name}</span>
                    </button>
                    <span className="flex gap-1">
                      <button
                        type="button"
                        className="text-xs text-[var(--odoo-primary)]"
                        disabled={idx === 0}
                        onClick={() => onMoveField?.(f.id, -1)}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        className="text-xs text-[var(--odoo-primary)]"
                        disabled={idx >= g.fields.length - 1}
                        onClick={() => onMoveField?.(f.id, 1)}
                      >
                        ↓
                      </button>
                    </span>
                  </li>
                ))}
                {g.fields.length === 0 && (
                  <li className="text-xs text-[var(--odoo-muted)]">Drop a field here</li>
                )}
              </ul>
            </div>
          ))}

          {notebooks.map((nb) => (
            <div
              key={nb.id}
              data-canvas-id={nb.id}
              className={`border border-[var(--odoo-border)] bg-white transition ring-offset-2 ${
                flashId === nb.id ? "ring-2 ring-[var(--odoo-primary)]" : ""
              }`}
            >
              <div className="flex flex-wrap gap-0 border-b border-[var(--odoo-border)] bg-[#faf9f8]">
                {nb.pages.map((page, i) => (
                  <div
                    key={page.id}
                    className={`border-r border-[var(--odoo-border)] px-3 py-1.5 text-xs font-semibold ${
                      i === 0
                        ? "bg-white text-[var(--odoo-primary)]"
                        : "text-[var(--odoo-muted)]"
                    }`}
                  >
                    {page.string || `Page ${i + 1}`}
                  </div>
                ))}
              </div>
              {nb.pages.map((page, i) => (
                <div
                  key={page.id}
                  data-canvas-id={page.id}
                  className={`p-2 ${i > 0 ? "border-t border-dashed border-[var(--odoo-border)]" : ""} ${
                    flashId === page.id ? "ring-2 ring-inset ring-[var(--odoo-primary)]" : ""
                  }`}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const name = e.dataTransfer.getData("text/odoo-field");
                    if (name && onDropFieldOnPage) onDropFieldOnPage(nb.id, page.id, name);
                  }}
                >
                  <div className="mb-1 text-[10px] uppercase tracking-wide text-[var(--odoo-muted)]">
                    Tab · {page.string}
                  </div>
                  <ul className="space-y-1">
                    {page.fields.map((f) => (
                      <li
                        key={f.id}
                        className="border border-[var(--odoo-border)] px-2 py-1 text-xs"
                      >
                        <span className="font-medium">{f.string || f.name}</span>
                        <span className="ml-2 font-mono text-[var(--odoo-muted)]">{f.name}</span>
                      </li>
                    ))}
                    {page.fields.length === 0 && (
                      <li className="text-xs text-[var(--odoo-muted)]">Drop a field on this tab</li>
                    )}
                  </ul>
                </div>
              ))}
            </div>
          ))}

          {groups.length === 0 && notebooks.length === 0 && (
            <p className="text-xs text-[var(--odoo-muted)]">
              Add a group or notebook, then drop fields from the palette.
            </p>
          )}
        </div>
        <div className="mt-4 border-t border-[var(--odoo-border)] bg-[#faf9f8] p-3">
          <div className="mb-2 flex gap-4 text-xs font-semibold text-[var(--odoo-primary)]">
            <span>Send message</span>
            <span className="text-[var(--odoo-muted)]">Log note</span>
            <span className="text-[var(--odoo-muted)]">Activities</span>
          </div>
          <div className="min-h-[48px] border border-[var(--odoo-border)] bg-white px-2 py-1.5 text-xs text-[var(--odoo-muted)]">
            Chatter · messages &amp; activities appear in Odoo after mail mixin
          </div>
        </div>
      </div>
    </div>
  );
}
