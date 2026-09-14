"use client";

import { useEffect, useState } from "react";
import type { PreviewHeaderButton, PreviewSmartButton, PreviewStatusBar } from "@/lib/draft-form-preview";
import { OdooButtonBox } from "@/components/odoo-preview/OdooButtonBox";
import { OdooChatterStub } from "@/components/odoo-preview/OdooChatterStub";
import { OdooFormHeader } from "@/components/odoo-preview/OdooFormHeader";
import { OdooFormSheet } from "@/components/odoo-preview/OdooFormSheet";

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
  count?: number | string | null;
};

export type CanvasHeaderButton = {
  id: string;
  string: string;
  variant?: "primary" | "secondary";
};

export type FormCanvasProps = {
  title: string;
  statusbar?: PreviewStatusBar | string | null;
  statusbarVisible?: string | null;
  /** Prefer `{ id, string }[]`. Plain strings are accepted for tests/legacy. */
  headerButtons?: Array<string | CanvasHeaderButton>;
  smartButtons?: CanvasSmartButton[];
  groups: CanvasGroup[];
  notebooks?: CanvasNotebook[];
  groupLayout?: "stack" | "two-column";
  flashId?: string | null;
  selectedFieldId?: string | null;
  onSelectField?: (fieldId: string) => void;
  onMoveField?: (fieldId: string, dir: -1 | 1) => void;
  onDropFieldName?: (groupId: string, fieldName: string) => void;
  onDropFieldOnPage?: (notebookId: string, pageId: string, fieldName: string) => void;
  showChatter?: boolean;
};

function normalizeHeaderButton(
  b: string | CanvasHeaderButton,
  index: number,
): PreviewHeaderButton {
  if (typeof b === "string") {
    return { id: `hdr-${index}-${b}`, string: b, variant: "secondary" };
  }
  return {
    id: b.id || `hdr-${index}`,
    string: b.string || "Button",
    variant: b.variant || "secondary",
  };
}

function resolveStatusbar(
  statusbar: PreviewStatusBar | string | null | undefined,
  statusbarVisible?: string | null,
): PreviewStatusBar | null {
  if (!statusbar) return null;
  if (typeof statusbar !== "string") return statusbar;
  const stages = (statusbarVisible || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (stages.length === 0) {
    return { field: statusbar, stages: [statusbar], activeStage: statusbar };
  }
  return { field: statusbar, stages, activeStage: stages[0] };
}

export function FormCanvas({
  title,
  statusbar,
  statusbarVisible,
  headerButtons = [],
  smartButtons = [],
  groups,
  notebooks = [],
  groupLayout = "stack",
  flashId = null,
  selectedFieldId,
  onSelectField,
  onMoveField,
  onDropFieldName,
  onDropFieldOnPage,
  showChatter = true,
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

  const headerBtns = headerButtons.map(normalizeHeaderButton);
  const statusbarSpec = resolveStatusbar(statusbar, statusbarVisible);
  const statButtons: PreviewSmartButton[] = smartButtons.map((b) => ({
    id: b.id,
    string: b.string,
    count: b.count,
  }));
  const twoColumn = groupLayout === "two-column" || groups.length >= 2;
  const [activePages, setActivePages] = useState<Record<string, string>>({});

  return (
    <div
      className="odoo-form-canvas overflow-hidden shadow-sm"
      data-testid="form-canvas"
      tabIndex={0}
    >
      <OdooFormHeader
        title={title}
        statusbar={statusbarSpec}
        headerButtons={headerBtns}
      />
      <OdooFormSheet>
        <OdooButtonBox buttons={statButtons} />
        <div className={`odoo-form-grid-2col ${twoColumn ? "is-two-column" : ""}`}>
          {groups.map((g) => (
            <div
              key={g.id}
              data-canvas-id={g.id}
              className={`odoo-field-group border border-[var(--odoo-border)] bg-white p-2 transition ring-offset-2 ${
                flashId === g.id ? "ring-2 ring-[var(--odoo-primary)]" : ""
              }`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const name = e.dataTransfer.getData("text/odoo-field");
                if (name && onDropFieldName) onDropFieldName(g.id, name);
              }}
            >
              <div className="odoo-field-group-title">{g.string || "Group"}</div>
              <ul className="space-y-1">
                {g.fields.map((f, idx) => (
                  <li
                    key={f.id}
                    className={`flex items-center justify-between gap-2 border px-2 py-1 text-sm ${
                      selectedFieldId === f.id
                        ? "border-[var(--odoo-primary)] bg-[color-mix(in_srgb,var(--odoo-primary)_8%,white)]"
                        : "border-[var(--odoo-border)]"
                    }`}
                  >
                    <button
                      type="button"
                      className="flex-1 text-left text-xs"
                      onClick={() => onSelectField?.(f.id)}
                    >
                      <span className="font-sans font-medium text-[var(--odoo-sheet-fg)]">
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
        </div>

        {notebooks.map((nb) => {
          const activePageId = activePages[nb.id] || nb.pages[0]?.id;
          const activePage =
            nb.pages.find((p) => p.id === activePageId) || nb.pages[0];
          return (
            <div
              key={nb.id}
              data-canvas-id={nb.id}
              className={`mt-4 border border-[var(--odoo-border)] bg-white transition ring-offset-2 ${
                flashId === nb.id ? "ring-2 ring-[var(--odoo-primary)]" : ""
              }`}
            >
              <div className="flex flex-wrap border-b border-[var(--odoo-border)] bg-[color-mix(in_srgb,var(--odoo-canvas)_50%,white)]">
                {nb.pages.map((page) => (
                  <button
                    key={page.id}
                    type="button"
                    className={`border-r border-[var(--odoo-border)] px-3 py-1.5 text-xs font-semibold ${
                      page.id === activePage?.id
                        ? "bg-white text-[var(--odoo-primary)]"
                        : "text-[var(--odoo-muted)]"
                    }`}
                    onClick={() =>
                      setActivePages((prev) => ({ ...prev, [nb.id]: page.id }))
                    }
                  >
                    {page.string || "Page"}
                  </button>
                ))}
              </div>
              {activePage ? (
                <div
                  data-canvas-id={activePage.id}
                  className={`p-2 ${
                    flashId === activePage.id
                      ? "ring-2 ring-inset ring-[var(--odoo-primary)]"
                      : ""
                  }`}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const name = e.dataTransfer.getData("text/odoo-field");
                    if (name && onDropFieldOnPage) {
                      onDropFieldOnPage(nb.id, activePage.id, name);
                    }
                  }}
                >
                  <ul className="space-y-1">
                    {activePage.fields.map((f) => (
                      <li
                        key={f.id}
                        className="border border-[var(--odoo-border)] px-2 py-1 text-xs"
                      >
                        <span className="font-medium">{f.string || f.name}</span>
                        <span className="ml-2 font-mono text-[var(--odoo-muted)]">
                          {f.name}
                        </span>
                      </li>
                    ))}
                    {activePage.fields.length === 0 && (
                      <li className="text-xs text-[var(--odoo-muted)]">
                        Drop a field on this tab
                      </li>
                    )}
                  </ul>
                </div>
              ) : null}
            </div>
          );
        })}

        {groups.length === 0 && notebooks.length === 0 && (
          <p className="text-xs text-[var(--odoo-muted)]">
            Add a group or notebook, then drop fields from the palette.
          </p>
        )}

        {showChatter ? <OdooChatterStub density="compact" /> : null}
      </OdooFormSheet>
    </div>
  );
}
