"use client";

import { useEffect, useRef, useState } from "react";
import { IconSnapshots, IconUndo } from "@/components/ui/icons";
import type { StudioTurn } from "@/lib/studio-session";
import { refineHistoryItems } from "@/lib/studio-session";

function formatTurnAt(at: string | undefined): string | null {
  if (!at) return null;
  const d = new Date(at);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function RefineHistoryPopover({
  conversation,
  onReuse,
  onUndo,
  undoBusy,
}: {
  conversation: StudioTurn[] | undefined;
  onReuse: (content: string) => void;
  onUndo: (instruction: string) => void;
  undoBusy?: boolean;
}) {
  const items = refineHistoryItems(conversation);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(ev: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(ev.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(ev: KeyboardEvent) {
      if (ev.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="studio-history" ref={rootRef}>
      <button
        type="button"
        className="btn btn-secondary btn-icon"
        aria-label="Refine history"
        aria-expanded={open}
        aria-haspopup="dialog"
        title={
          items.length
            ? `Refine history (${items.length}) — Undo uses restore/oops; click a phrase to reuse it`
            : "Refine history — no changes yet"
        }
        data-testid="refine-history"
        onClick={() => setOpen((v) => !v)}
      >
        <IconSnapshots className="h-4 w-4" aria-hidden />
        {items.length ? (
          <span className="studio-history-count" aria-hidden>
            {items.length > 9 ? "9+" : items.length}
          </span>
        ) : null}
      </button>
      {open ? (
        <div className="studio-history-pop" role="dialog" aria-label="Refine history">
          {items.length === 0 ? (
            <p className="studio-history-empty">No refinements yet. Chat changes appear here.</p>
          ) : (
            <ul className="studio-history-list">
              {items.map((item, idx) => (
                <li
                  key={`${item.at || idx}-${item.content.slice(0, 24)}`}
                  className="studio-history-row"
                >
                  <button
                    type="button"
                    className="studio-history-item"
                    title="Reuse this phrase in the composer"
                    onClick={() => {
                      onReuse(item.content);
                      setOpen(false);
                    }}
                  >
                    <span className="studio-history-item-text">{item.content}</span>
                    {formatTurnAt(item.at) ? (
                      <span className="studio-history-item-at">{formatTurnAt(item.at)}</span>
                    ) : null}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm studio-history-undo"
                    data-testid={item.isLatest ? "refine-history-undo-latest" : undefined}
                    disabled={undoBusy || !item.undoInstruction}
                    title={
                      item.undoInstruction
                        ? item.isLatest
                          ? `Undo this change (sends “oops”)`
                          : `Undo via “${item.undoInstruction}”`
                        : "Type restore/oops in chat for this one"
                    }
                    onClick={() => {
                      if (!item.undoInstruction) return;
                      onUndo(item.undoInstruction);
                      setOpen(false);
                    }}
                  >
                    <IconUndo className="h-3.5 w-3.5" aria-hidden />
                    Undo
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
