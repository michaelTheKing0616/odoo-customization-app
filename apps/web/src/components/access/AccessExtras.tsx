"use client";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import { Select } from "@/components/ui/Select";
import type { GroupRow } from "@/lib/api";

type AccessExtrasProps = {
  model: string;
  busy?: boolean;
  groups: GroupRow[];
  mcGuidance: { title: string; body: string } | null;
  docsGate: { available: boolean; message?: string | null } | null;
  docsFolders: Array<{ id: number; name: string | null }>;
  docsFolderId: string;
  docsMapping: Record<string, number>;
  onDocsFolderId: (value: string) => void;
  onApplyMultiCompany: () => void;
  onLoadFolders: () => void;
  onSaveFolder: () => void;
};

export function AccessExtras({
  model,
  busy,
  groups,
  mcGuidance,
  docsGate,
  docsFolders,
  docsFolderId,
  docsMapping,
  onDocsFolderId,
  onApplyMultiCompany,
  onLoadFolders,
  onSaveFolder,
}: AccessExtrasProps) {
  return (
    <div className="space-y-4">
      <Card className="p-5" data-testid="access-groups">
        <h2 className="text-sm font-semibold text-ink">Security groups</h2>
        <p className="mt-1 text-xs text-muted">
          Groups loaded from this instance. Use them in access lines and record rules — this list
          is read-only.
        </p>
        <ul className="mt-3 max-h-40 space-y-1 overflow-auto text-sm">
          {groups.map((g) => (
            <li
              key={g.id}
              className="border-l-2 border-border-subtle pl-3 text-ink"
              style={{ marginLeft: g.full_name?.includes("/") ? 12 : 0 }}
            >
              <span className="font-mono text-accent">{g.name}</span>
              {g.full_name ? <span className="ml-2 text-muted">{g.full_name}</span> : null}
            </li>
          ))}
          {groups.length === 0 ? (
            <li className="text-muted">No groups loaded yet.</li>
          ) : null}
        </ul>
      </Card>

      <Card className="p-5">
        <h2 className="text-sm font-semibold text-ink">
          {mcGuidance?.title ?? "Multi-company pack"}
        </h2>
        <p className="mt-2 text-sm text-muted">
          {mcGuidance?.body ??
            "Adds x_company_id plus a global record rule with a company_ids domain on custom models."}
        </p>
        <p className="mt-2 text-xs text-muted">
          Confirm with the phrase before apply. This writes live Odoo and must not create a global
          ir.rule without confirmation.
        </p>
        <Button
          type="button"
          variant="secondary"
          className="mt-3"
          disabled={busy || !model.startsWith("x_")}
          onClick={onApplyMultiCompany}
          data-testid="access-apply-live-pack"
        >
          Apply live pack to loaded model
        </Button>
      </Card>

      <Card className="p-5">
        <h2 className="text-sm font-semibold text-ink">Documents folder map</h2>
        <p className="mt-1 text-xs text-muted">
          {docsGate?.available
            ? "Map custom models to a Documents folder (Enterprise documents module)."
            : (docsGate?.message ??
              "Documents module not available — config is stored but attach automation is suggestion-only.")}
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={busy || !docsGate?.available}
            onClick={onLoadFolders}
          >
            Load folders
          </Button>
          <Select
            options={[
              { value: "", label: "Select folder" },
              ...docsFolders.map((f) => ({
                value: String(f.id),
                label: f.name ?? `#${f.id}`,
              })),
            ]}
            value={docsFolderId}
            onChange={(e) => onDocsFolderId(e.target.value)}
            disabled={docsFolders.length === 0}
          />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={busy || !model.startsWith("x_") || !docsFolderId}
            onClick={onSaveFolder}
          >
            Save for loaded model
          </Button>
        </div>
        {Object.keys(docsMapping).length > 0 ? (
          <ul className="mt-3 space-y-1 font-mono text-xs text-muted">
            {Object.entries(docsMapping).map(([m, fid]) => (
              <li key={m}>
                {m} → folder {fid}
              </li>
            ))}
          </ul>
        ) : null}
      </Card>
    </div>
  );
}
