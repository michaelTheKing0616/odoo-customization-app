"use client";

import { useMemo, useState } from "react";
import {
  RENTAL_AGREEMENT_STARTER,
  ReportBlock,
  ReportCanvas,
} from "@/components/reports/ReportCanvas";

/**
 * PDF-01 vision harness — mounts ReportCanvas alone for before/after shots.
 * Gated by NEXT_PUBLIC_E2E (same pattern as designer-premium).
 */
export default function ReportCanvasHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [blocks, setBlocks] = useState<ReportBlock[]>(RENTAL_AGREEMENT_STARTER);
  const [selectedId, setSelectedId] = useState<string | null>("h1");
  const [empty, setEmpty] = useState(false);

  const shown = useMemo(() => (empty ? [] : blocks), [blocks, empty]);

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  function moveBlock(id: string, dir: -1 | 1) {
    setBlocks((prev) => {
      const idx = prev.findIndex((b) => b.id === id);
      if (idx < 0) return prev;
      const next = idx + dir;
      if (next < 0 || next >= prev.length) return prev;
      const copy = [...prev];
      const [item] = copy.splice(idx, 1);
      copy.splice(next, 0, item);
      return copy;
    });
  }

  return (
    <main
      className="min-h-screen bg-background p-8 text-ink"
      data-testid="report-canvas-harness"
    >
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-sm font-medium text-muted">PDF-01 ReportCanvas harness</h1>
        <button
          type="button"
          data-testid="harness-toggle-empty"
          className="rounded border border-border-subtle px-2 py-1 text-xs"
          onClick={() => setEmpty((v) => !v)}
        >
          {empty ? "Show blocks" : "Show empty"}
        </button>
        <button
          type="button"
          data-testid="harness-theme-toggle"
          className="rounded border border-border-subtle px-2 py-1 text-xs"
          onClick={() => {
            document.documentElement.classList.toggle("dark");
          }}
        >
          Toggle theme
        </button>
      </div>
      <div data-testid="report-canvas-stage" className="mx-auto max-w-[720px]">
        <ReportCanvas
          blocks={shown}
          paperLabel="A4"
          useExternalLayout
          selectedId={selectedId}
          onSelect={setSelectedId}
          onMove={moveBlock}
          onAddBlock={() =>
            setBlocks((prev) => [
              ...prev,
              {
                id: `b_${Date.now()}`,
                type: "text",
                text: "New paragraph",
              },
            ])
          }
          documentTitle="Rental Agreement"
        />
      </div>
    </main>
  );
}
