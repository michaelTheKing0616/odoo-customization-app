"use client";

import { useEffect, type ComponentProps } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Kbd } from "@/components/ui/layout-primitives";
import { Tooltip } from "@/components/ui/Tooltip";
import { IconRedo, IconUndo } from "@/components/ui/icons";

export type DesignerPublishState = "draft" | "unpublished" | "published";

const STATE_COPY: Record<
  DesignerPublishState,
  { label: string; variant: ComponentProps<typeof Badge>["variant"]; hint: string }
> = {
  unpublished: {
    label: "Unpublished",
    variant: "warning",
    hint: "Canvas edits stay local until you Save to Odoo.",
  },
  published: {
    label: "Published",
    variant: "success",
    hint: "Matches the last inherit save. Session undo is empty — restore a published checkpoint to revert Odoo.",
  },
  draft: {
    label: "Draft",
    variant: "default",
    hint: "Not saved to Odoo yet. Undo/redo applies to this session only.",
  },
};

type DesignerSessionBarProps = {
  publishState: DesignerPublishState;
  canUndo: boolean;
  canRedo: boolean;
  canRollbackPublish: boolean;
  undoLabel?: string;
  redoLabel?: string;
  busy?: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onRollbackPublish: () => void;
  onEmptyUndo?: () => void;
};

function isDialogTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && Boolean(target.closest('[role="dialog"]'));
}

export function DesignerSessionBar({
  publishState,
  canUndo,
  canRedo,
  canRollbackPublish,
  undoLabel,
  redoLabel,
  busy,
  onUndo,
  onRedo,
  onRollbackPublish,
  onEmptyUndo,
}: DesignerSessionBarProps) {
  const copy = STATE_COPY[publishState];

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (!(event.metaKey || event.ctrlKey)) return;
      if (isDialogTarget(event.target)) return;
      const key = event.key.toLowerCase();
      const redo = (key === "z" && event.shiftKey) || key === "y";
      const undo = key === "z" && !event.shiftKey;
      if (!undo && !redo) return;
      if (undo) {
        event.preventDefault();
        if (canUndo && !busy) onUndo();
        else onEmptyUndo?.();
        return;
      }
      if (canRedo && !busy) {
        event.preventDefault();
        onRedo();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, canRedo, canUndo, onEmptyUndo, onRedo, onUndo]);

  const undoTitle = canUndo
    ? `Undo ${undoLabel ?? "last canvas edit"}`
    : "No unpublished canvas edits. Restore a published checkpoint to revert Odoo.";
  const redoTitle = canRedo
    ? `Redo ${redoLabel ?? "canvas edit"}`
    : "Nothing to redo";

  return (
    <div
      className="mt-4 flex flex-wrap items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-3 py-2 shadow-subtle"
      data-testid="designer-session-bar"
    >
      <span data-testid="designer-publish-state">
        <Badge variant={copy.variant}>{copy.label}</Badge>
      </span>
      <p className="mr-auto max-w-xl text-xs text-muted" data-testid="designer-session-hint">
        {copy.hint}
      </p>
      <Tooltip label={undoTitle}>
        <span className="inline-flex">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={busy || !canUndo}
            onClick={onUndo}
            data-testid="designer-undo"
            aria-label="Undo"
            title={undoTitle}
          >
            <IconUndo className="h-3.5 w-3.5" aria-hidden />
            Undo
            <Kbd>⌘Z</Kbd>
          </Button>
        </span>
      </Tooltip>
      <Tooltip label={redoTitle}>
        <span className="inline-flex">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={busy || !canRedo}
            onClick={onRedo}
            data-testid="designer-redo"
            aria-label="Redo"
            title={redoTitle}
          >
            <IconRedo className="h-3.5 w-3.5" aria-hidden />
            Redo
            <Kbd>⌘⇧Z</Kbd>
          </Button>
        </span>
      </Tooltip>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={busy || !canRollbackPublish}
        onClick={onRollbackPublish}
        data-testid="designer-rollback-publish"
        title={
          canRollbackPublish
            ? "Restore the snapshot taken before the last Save to Odoo"
            : "No published checkpoint yet"
        }
      >
        Roll back last publish
      </Button>
    </div>
  );
}

export function designerPublishState(opts: {
  dirty: boolean;
  hasPublishedView: boolean;
}): DesignerPublishState {
  if (opts.dirty) return "unpublished";
  if (opts.hasPublishedView) return "published";
  return "draft";
}
