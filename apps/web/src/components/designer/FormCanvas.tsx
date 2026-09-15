"use client";

import { useEffect, useRef, useState, type DragEvent } from "react";
import type { PreviewHeaderButton, PreviewSmartButton, PreviewStatusBar } from "@/lib/draft-form-preview";
import {
  attachDragGhost,
  insertIndexFromElements,
  readCanvasFieldId,
  readPaletteFieldName,
  setCanvasFieldDragData,
} from "@/lib/designer-dnd";
import { OdooButtonBox } from "@/components/odoo-preview/OdooButtonBox";
import { OdooChatterStub } from "@/components/odoo-preview/OdooChatterStub";
import { OdooField } from "@/components/odoo-preview/OdooField";
import { OdooFormHeader } from "@/components/odoo-preview/OdooFormHeader";
import { OdooFormSheet } from "@/components/odoo-preview/OdooFormSheet";
import { cn } from "@/lib/cn";

/**
 * Interactive Odoo-looking form canvas for View Designer.
 * Structural preview — Open-in-Odoo / live iframe remains authoritative.
 */

export type CanvasField = {
  id: string;
  name: string;
  string?: string;
  ttype?: string;
  widget?: string;
  required?: boolean;
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
  headerButtons?: Array<string | CanvasHeaderButton>;
  smartButtons?: CanvasSmartButton[];
  groups: CanvasGroup[];
  notebooks?: CanvasNotebook[];
  groupLayout?: "stack" | "two-column";
  flashId?: string | null;
  selectedFieldId?: string | null;
  onSelectField?: (fieldId: string) => void;
  onMoveField?: (fieldId: string, dir: -1 | 1) => void;
  onDropFieldName?: (groupId: string, fieldName: string, index?: number) => void;
  onDropFieldOnPage?: (notebookId: string, pageId: string, fieldName: string, index?: number) => void;
  onReorderField?: (fieldId: string, groupId: string, index: number) => void;
  onReorderPageField?: (
    fieldId: string,
    notebookId: string,
    pageId: string,
    index: number,
  ) => void;
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

function DroppableFieldList({
  items,
  selectedFieldId,
  flashId,
  onSelectField,
  onPaletteDrop,
  onCanvasReorder,
}: {
  items: CanvasField[];
  selectedFieldId?: string | null;
  flashId?: string | null;
  onSelectField?: (fieldId: string) => void;
  onPaletteDrop: (fieldName: string, index: number) => void;
  onCanvasReorder?: (fieldId: string, index: number) => void;
}) {
  const listRef = useRef<HTMLDivElement | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);

  function itemEls(): HTMLElement[] {
    if (!listRef.current) return [];
    return Array.from(listRef.current.querySelectorAll<HTMLElement>("[data-canvas-field]"));
  }

  function onDragOver(e: DragEvent) {
    e.preventDefault();
    const els = itemEls();
    const index = insertIndexFromElements(e.clientY, els);
    setDropIndex(index);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    const els = itemEls();
    const index = insertIndexFromElements(e.clientY, els);
    const canvasId = readCanvasFieldId(e.dataTransfer);
    if (canvasId && onCanvasReorder) {
      onCanvasReorder(canvasId, index);
    } else {
      const name = readPaletteFieldName(e.dataTransfer);
      if (name) onPaletteDrop(name, index);
    }
    setDropIndex(null);
  }

  return (
    <div
      ref={listRef}
      className={cn("designer-drop-list relative min-h-[2.5rem]", dropIndex !== null && "is-over")}
      data-testid="canvas-drop-list"
      onDragOver={onDragOver}
      onDragLeave={(e) => {
        if (!listRef.current?.contains(e.relatedTarget as Node)) setDropIndex(null);
      }}
      onDrop={onDrop}
    >
      {items.map((f, idx) => (
        <div
          key={f.id}
          data-canvas-field
          data-field-id={f.id}
          data-testid={`canvas-field-${f.name}`}
          draggable={Boolean(onCanvasReorder)}
          onDragStart={(e) => {
            setCanvasFieldDragData(e.dataTransfer, f.id, f.name);
            attachDragGhost(e.dataTransfer, f.string || f.name, e.currentTarget);
          }}
          className={cn(
            "designer-canvas-field relative",
            selectedFieldId === f.id && "is-selected",
            flashId === f.id && "is-flash",
            dropIndex === idx && "drop-before",
          )}
        >
          {dropIndex === idx ? <span className="designer-drop-line" aria-hidden /> : null}
          <OdooField
            field={{
              id: f.id,
              name: f.name,
              string: f.string || f.name,
              ttype: f.ttype || "char",
              widget: f.widget,
              required: f.required,
            }}
            highlighted={selectedFieldId === f.id}
            onClick={() => onSelectField?.(f.id)}
          />
        </div>
      ))}
      {dropIndex === items.length ? <span className="designer-drop-line" aria-hidden /> : null}
      {items.length === 0 && dropIndex === null ? (
        <p className="px-1 py-3 text-xs text-[var(--odoo-muted)]">Drop a field here</p>
      ) : null}
    </div>
  );
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
  onReorderField,
  onReorderPageField,
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
      move(fieldId, e.key === "ArrowDown" ? 1 : -1);
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
              className={cn(
                "odoo-field-group rounded-sm border border-transparent p-1 transition",
                flashId === g.id && "ring-2 ring-[var(--odoo-primary)]",
              )}
            >
              <div className="odoo-field-group-title">{g.string || "Group"}</div>
              <DroppableFieldList
                items={g.fields}
                selectedFieldId={selectedFieldId}
                flashId={flashId}
                onSelectField={onSelectField}
                onPaletteDrop={(name, index) => onDropFieldName?.(g.id, name, index)}
                onCanvasReorder={
                  onReorderField
                    ? (fieldId, index) => onReorderField(fieldId, g.id, index)
                    : undefined
                }
              />
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
              className={cn(
                "odoo-notebook mt-4 border border-[var(--odoo-border)] bg-surface transition",
                flashId === nb.id && "ring-2 ring-[var(--odoo-primary)]",
              )}
            >
              <div className="flex flex-wrap border-b border-[var(--odoo-border)] bg-[color-mix(in_srgb,var(--odoo-canvas)_50%,var(--surface))]">
                {nb.pages.map((page) => (
                  <button
                    key={page.id}
                    type="button"
                    className={cn(
                      "border-r border-[var(--odoo-border)] px-3 py-1.5 text-xs font-semibold",
                      page.id === activePage?.id
                        ? "bg-surface text-[var(--odoo-primary)]"
                        : "text-[var(--odoo-muted)]",
                    )}
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
                  className={cn(
                    "p-2",
                    flashId === activePage.id && "ring-2 ring-inset ring-[var(--odoo-primary)]",
                  )}
                >
                  <DroppableFieldList
                    items={activePage.fields}
                    selectedFieldId={selectedFieldId}
                    flashId={flashId}
                    onSelectField={onSelectField}
                    onPaletteDrop={(name, index) =>
                      onDropFieldOnPage?.(nb.id, activePage.id, name, index)
                    }
                    onCanvasReorder={
                      onReorderPageField
                        ? (fieldId, index) =>
                            onReorderPageField(fieldId, nb.id, activePage.id, index)
                        : undefined
                    }
                  />
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
