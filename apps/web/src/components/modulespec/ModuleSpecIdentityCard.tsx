"use client";

import { Card } from "@/components/ui/layout-primitives";
import type { ModuleSpecDoc } from "@/lib/modulespec-types";
import { moduleSpecSummary, type ModuleSpecSummary } from "@/lib/modulespec-journey";

type ModuleSpecIdentityCardProps = {
  value: ModuleSpecDoc;
  readOnly?: boolean;
  barcodeModuleAllowed?: boolean;
  onChange: (next: ModuleSpecDoc) => void;
};

export function ModuleSpecIdentityCard({
  value,
  readOnly,
  barcodeModuleAllowed,
  onChange,
}: ModuleSpecIdentityCardProps) {
  const summary: ModuleSpecSummary = moduleSpecSummary(value);
  function patch(partial: Partial<ModuleSpecDoc>) {
    onChange({ ...value, ...partial });
  }
  return (
    <Card className="p-5" data-testid="modulespec-identity">
      <h2 className="text-lg font-semibold text-ink">App identity</h2>
      <p className="mt-1 text-sm text-muted">
        Technical name becomes the module directory. Depends are Community apps this IR needs.
      </p>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label className="studio-field-stack text-sm">
          <span className="studio-field-label">Display name</span>
          <input
            disabled={readOnly}
            value={String(value.display_name ?? "")}
            onChange={(event) => patch({ display_name: event.target.value })}
            className="input"
            data-testid="modulespec-display-name"
          />
        </label>
        <label className="studio-field-stack text-sm">
          <span className="studio-field-label">Technical name</span>
          <input
            disabled={readOnly}
            value={String(value.technical_name ?? "")}
            onChange={(event) => patch({ technical_name: event.target.value })}
            className="input font-mono"
            data-testid="modulespec-technical-name"
          />
        </label>
        <label className="studio-field-stack text-sm md:col-span-2">
          <span className="studio-field-label">Depends</span>
          <input
            disabled={readOnly}
            value={(value.depends || []).join(", ")}
            onChange={(event) =>
              patch({
                depends: event.target.value
                  .split(",")
                  .map((part) => part.trim())
                  .filter(Boolean),
              })
            }
            className="input font-mono"
            data-testid="modulespec-depends"
          />
        </label>
      </div>
      <p className="mt-3 text-xs text-muted" data-testid="modulespec-identity-summary">
        {summary.models} models · {summary.fields} fields · {summary.views} views · {summary.menus}{" "}
        menus · {summary.access} access
      </p>
      {barcodeModuleAllowed ? (
        <label className="mt-3 flex items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={Boolean(value.include_barcode_scan_widget)}
            onChange={(event) => patch({ include_barcode_scan_widget: event.target.checked })}
          />
          Include exported <code className="text-xs">x_barcode_scan</code> OWL widget module
        </label>
      ) : (
        <p className="mt-3 text-xs text-muted">
          Exported barcode widget module is unavailable on Odoo Online — use Bulk Suite in-app
          scanner instead.
        </p>
      )}
    </Card>
  );
}
