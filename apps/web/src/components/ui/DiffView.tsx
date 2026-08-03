"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

export type DiffLine = { type: "add" | "remove" | "context"; text: string };

type DiffViewProps = {
  before: string;
  after: string;
  className?: string;
};

function computeUnified(before: string, after: string): DiffLine[] {
  const a = before.split("\n");
  const b = after.split("\n");
  const lines: DiffLine[] = [];
  const max = Math.max(a.length, b.length);
  for (let i = 0; i < max; i++) {
    const left = a[i];
    const right = b[i];
    if (left === right) {
      if (left !== undefined) lines.push({ type: "context", text: left });
      continue;
    }
    if (left !== undefined) lines.push({ type: "remove", text: left });
    if (right !== undefined) lines.push({ type: "add", text: right });
  }
  return lines;
}

export function DiffView({ before, after, className }: DiffViewProps) {
  const [mode, setMode] = useState<"unified" | "split">("unified");
  const unified = useMemo(() => computeUnified(before, after), [before, after]);

  return (
    <div className={cn("rounded-md border border-border-subtle", className)} data-testid="diff-view">
      <div className="flex items-center justify-between border-b border-border-subtle px-3 py-2">
        <span className="text-sm font-medium text-ink">Diff</span>
        <div className="flex gap-2">
          <Button
            variant={mode === "unified" ? "secondary" : "ghost"}
            size="sm"
            type="button"
            onClick={() => setMode("unified")}
          >
            Unified
          </Button>
          <Button
            variant={mode === "split" ? "secondary" : "ghost"}
            size="sm"
            type="button"
            onClick={() => setMode("split")}
          >
            Side by side
          </Button>
        </div>
      </div>
      {mode === "unified" ? (
        <pre className="max-h-80 overflow-auto p-3 font-mono text-xs">
          {unified.map((line, i) => (
            <div
              key={`${line.type}-${i}`}
              className={cn(
                line.type === "add" && "bg-success-subtle text-success",
                line.type === "remove" && "bg-danger-subtle text-danger",
              )}
            >
              {line.type === "add" ? "+ " : line.type === "remove" ? "- " : "  "}
              {line.text}
            </div>
          ))}
        </pre>
      ) : (
        <div className="grid max-h-80 grid-cols-2 divide-x divide-border-subtle overflow-auto">
          <pre className="p-3 font-mono text-xs text-danger">{before}</pre>
          <pre className="p-3 font-mono text-xs text-success">{after}</pre>
        </div>
      )}
    </div>
  );
}
