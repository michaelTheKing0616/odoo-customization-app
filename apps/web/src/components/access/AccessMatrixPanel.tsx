"use client";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import type { AccessMatrixOut } from "@/lib/api";
import { cn } from "@/lib/cn";

type AccessMatrixPanelProps = {
  modelsInput: string;
  onModelsInput: (value: string) => void;
  matrix: AccessMatrixOut | null;
  busy?: boolean;
  canMutate?: boolean;
  mutateBlocked?: string | null;
  onLoad: () => void;
  onToggle: (
    cell: AccessMatrixOut["cells"][number],
    groupId: number | null,
    key: "perm_read" | "perm_write" | "perm_create" | "perm_unlink",
  ) => void;
  cellFor: (modelName: string, groupId: number | null) => AccessMatrixOut["cells"][number];
};

const PERM_KEYS = [
  ["perm_read", "R"],
  ["perm_write", "W"],
  ["perm_create", "C"],
  ["perm_unlink", "D"],
] as const;

export function AccessMatrixPanel({
  modelsInput,
  onModelsInput,
  matrix,
  busy,
  canMutate = true,
  mutateBlocked,
  onLoad,
  onToggle,
  cellFor,
}: AccessMatrixPanelProps) {
  return (
    <Card className="p-5" data-testid="access-matrix">
      <h2 className="text-sm font-semibold text-ink">Access matrix</h2>
      <p className="mt-1 text-xs text-muted">
        Groups × models. Toggle R/W/C/D. An empty cell creates a new access line for that group.
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <Input
          label="Models (comma-separated)"
          value={modelsInput}
          onChange={(e) => onModelsInput(e.target.value)}
          className="w-full max-w-md font-mono"
        />
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          loading={busy}
          onClick={onLoad}
        >
          Load matrix
        </Button>
      </div>
      {matrix ? (
        <div className="mt-4 overflow-auto">
          <table className="min-w-full text-left text-xs">
            <thead className="text-muted">
              <tr>
                <th className="sticky left-0 bg-surface-raised py-2 pr-3">Group / model</th>
                {matrix.models.map((m) => (
                  <th key={m} className="px-2 py-2 font-mono">
                    {m}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.groups.slice(0, 40).map((g) => (
                <tr key={g.id} className="border-t border-border-subtle">
                  <td className="sticky left-0 bg-surface-raised py-2 pr-3 text-accent">
                    {g.full_name || g.name}
                  </td>
                  {matrix.models.map((m) => {
                    const cell = cellFor(m, g.id);
                    return (
                      <td key={`${m}-${g.id}`} className="px-2 py-2">
                        <div className="flex gap-1 font-mono">
                          {PERM_KEYS.map(([key, label]) => (
                            <button
                              key={key}
                              type="button"
                              disabled={busy || !canMutate}
                              title={mutateBlocked ?? `${label} ${cell[key] ? "on" : "off"}`}
                              onClick={() => void onToggle(cell, g.id, key)}
                              className={cn(
                                "rounded px-1",
                                cell[key]
                                  ? "bg-accent text-on-accent"
                                  : "border border-border-subtle text-muted",
                              )}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          {matrix.groups.length > 40 ? (
            <p className="mt-2 text-xs text-muted">
              Showing first 40 groups of {matrix.groups.length}.
            </p>
          ) : null}
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted">Load the matrix to edit group grants in bulk.</p>
      )}
    </Card>
  );
}
