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
    <div className="designer-palette-group mt-5" data-testid="niche-widget-palette">
      <h3 className="designer-palette-heading">
        <span>Odoo widgets</span>
        <span className="designer-palette-count">{widgets.length}</span>
      </h3>
      <ul className="space-y-px">
        {widgets.map((w) => (
          <li key={w.id}>
            <button
              type="button"
              className="designer-palette-item w-full cursor-pointer text-start"
              onClick={() => onPick(w)}
            >
              <span className="designer-palette-label">{w.label}</span>
              <span className="designer-palette-name">{w.id}</span>
            </button>
          </li>
        ))}
      </ul>
      {colorPalette.length > 0 ? (
        <p className="mt-2 px-0.5 text-[11px] leading-snug text-subtle">
          Color indices: {colorPalette.map((c) => c.name).join(", ")}
        </p>
      ) : null}
    </div>
  );
}
