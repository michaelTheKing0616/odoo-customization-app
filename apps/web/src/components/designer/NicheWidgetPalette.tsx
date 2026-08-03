"use client";

export type NicheWidgetEntry = {
  id: string;
  label: string;
  recommended_ttypes: string[];
  hint?: string;
  supporting_field?: {
    name: string;
    ttype: string;
    string?: string;
    relation?: string;
  } | null;
};

export type ColorPaletteEntry = {
  index: number;
  name: string;
};

export function NicheWidgetPalette({
  widgets,
  colorPalette,
  onPick,
}: {
  widgets: NicheWidgetEntry[];
  colorPalette: ColorPaletteEntry[];
  onPick: (widget: NicheWidgetEntry) => void;
}) {
  if (widgets.length === 0 && colorPalette.length === 0) return null;
  return (
    <div className="odoo-sheet mt-2 max-h-56 overflow-auto p-2" data-testid="niche-widget-palette">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--odoo-muted)]">
        §15 widgets
      </p>
      <ul className="space-y-1">
        {widgets.map((w) => (
          <li key={w.id}>
            <button
              type="button"
              className="w-full border border-[var(--odoo-border)] bg-white px-2 py-1 text-left text-xs hover:bg-[#f5eef3]"
              onClick={() => onPick(w)}
            >
              <span className="font-mono text-[var(--odoo-primary)]">{w.id}</span>
              <span className="ml-2 text-[var(--odoo-muted)]">{w.label}</span>
            </button>
          </li>
        ))}
      </ul>
      {colorPalette.length > 0 ? (
        <p className="mt-2 text-[10px] text-[var(--odoo-muted)]">
          Color indices: {colorPalette.map((c) => c.name).join(", ")}
        </p>
      ) : null}
    </div>
  );
}
