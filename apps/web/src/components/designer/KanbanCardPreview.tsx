"use client";

import { ReorderableBlocks } from "@/components/ui/canvas/ReorderableBlocks";
import {
  DesignerGrip,
  DesignerPointerGhost,
  useDesignerPointerGhost,
} from "@/components/designer/DesignerPointerGhost";
import { ChevronDown, ChevronUp, X } from "@/components/ui/icons";
import { cn } from "@/lib/cn";

/**
 * Odoo-familiar kanban card preview for the View Designer.
 * Structural preview: Open in Odoo remains authoritative.
 * Labels (nolabel) are not in our kanban arch helpers yet, values only.
 * UI-S-12: board is a card on the desk; drag (UI-F13) and arrow keys reorder,
 * the step buttons are secondary and stay quiet until hover or focus.
 */

export type KanbanCardField = {
  id: string;
  name: string;
  string?: string;
};

export type KanbanCardPreviewProps = {
  title: string;
  groupBy?: string | null;
  fields: KanbanCardField[];
  selectedFieldId?: string | null;
  onSelectField?: (fieldId: string) => void;
  onMoveField?: (fieldId: string, dir: -1 | 1) => void;
  onRemoveField?: (fieldId: string) => void;
  onDropFieldName?: (fieldName: string) => void;
};

export function KanbanCardPreview({
  title,
  groupBy,
  fields,
  selectedFieldId,
  onSelectField,
  onMoveField,
  onRemoveField,
  onDropFieldName,
}: KanbanCardPreviewProps) {
  const trackGhost = useDesignerPointerGhost();
  const reorderable = Boolean(onMoveField);
  const columns = groupBy
    ? [
        { key: "a", label: "Column A" },
        { key: "b", label: "Column B" },
      ]
    : [{ key: "all", label: "All records" }];

  return (
    <div className="odoo-kanban-canvas overflow-hidden shadow-sm" data-testid="kanban-card-preview">
      <div className="designer-kanban-head">
        <span className="designer-kanban-title">{title}</span>
        {groupBy ? (
          <span className="designer-chip" data-testid="kanban-groupby-chip">
            Grouped by <code>{groupBy}</code>
          </span>
        ) : (
          <span className="designer-chip">Not grouped</span>
        )}
      </div>

      <div
        className="designer-kanban-board"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const name = e.dataTransfer.getData("text/odoo-field");
          if (name && onDropFieldName) onDropFieldName(name);
        }}
      >
        {columns.map((col, colIndex) => (
          <div key={col.key} className="designer-kanban-lane">
            <div className="designer-kanban-lane-title">{col.label}</div>
            <div className="designer-kanban-card">
              {fields.length === 0 ? (
                <p className="designer-drop-empty">Drop fields here to build the card</p>
              ) : (
                <ReorderableBlocks
                  as="ul"
                  itemAs="li"
                  items={fields}
                  getId={(f) => f.id}
                  disabled={!onMoveField}
                  onMove={onMoveField}
                  className="relative space-y-0.5"
                  itemProps={(f) => ({
                    ...(reorderable ? { "data-reorderable": "" } : {}),
                    onPointerMove: reorderable ? trackGhost : undefined,
                    "aria-label": `${f.string || f.name} (${f.name})`,
                    className: cn(
                      "designer-kanban-field",
                      selectedFieldId === f.id && "is-selected",
                    ),
                  })}
                >
                  {(f, idx, meta) => (
                    <>
                      {meta.isDropTarget ? <span className="designer-drop-line" aria-hidden /> : null}
                      {meta.dropIndex === fields.length && idx === fields.length - 1 ? (
                        <span className="designer-drop-line is-after" aria-hidden />
                      ) : null}
                      <div className="designer-row-body">
                        <button
                          type="button"
                          className="min-w-0 flex-1 text-start"
                          onClick={() => onSelectField?.(f.id)}
                        >
                          <div className="designer-row-label">{f.string || f.name}</div>
                          <div className="designer-row-name">{f.name}</div>
                          {idx === 0 && <div className="designer-row-sample">Sample value</div>}
                        </button>
                        <span className="designer-row-tools">
                          <button
                            type="button"
                            className="designer-row-tool"
                            disabled={idx === 0}
                            aria-label={`Move ${f.name} up`}
                            onPointerDown={(e) => e.stopPropagation()}
                            onClick={() => onMoveField?.(f.id, -1)}
                          >
                            <ChevronUp className="h-3.5 w-3.5" aria-hidden />
                          </button>
                          <button
                            type="button"
                            className="designer-row-tool"
                            disabled={idx >= fields.length - 1}
                            aria-label={`Move ${f.name} down`}
                            onPointerDown={(e) => e.stopPropagation()}
                            onClick={() => onMoveField?.(f.id, 1)}
                          >
                            <ChevronDown className="h-3.5 w-3.5" aria-hidden />
                          </button>
                          {onRemoveField && (
                            <button
                              type="button"
                              className="designer-row-tool is-danger"
                              aria-label={`Remove ${f.name}`}
                              onPointerDown={(e) => e.stopPropagation()}
                              onClick={() => onRemoveField(f.id)}
                            >
                              <X className="h-3.5 w-3.5" aria-hidden />
                            </button>
                          )}
                        </span>
                      </div>
                      {reorderable ? <DesignerGrip /> : null}
                      {meta.isDragging ? (
                        <DesignerPointerGhost label={f.string || f.name} name={f.name} />
                      ) : null}
                    </>
                  )}
                </ReorderableBlocks>
              )}
            </div>
            {colIndex === 0 && fields.length > 0 && (
              <div className="designer-kanban-card is-ghost">More cards in this column</div>
            )}
          </div>
        ))}
      </div>

      <div className="designer-card-foot">
        Card field order matches the saved kanban arch. Open in Odoo is authoritative.
      </div>
    </div>
  );
}
