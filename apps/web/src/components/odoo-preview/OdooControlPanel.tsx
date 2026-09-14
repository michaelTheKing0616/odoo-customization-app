"use client";

type PreviewViewTab = "form" | "list" | "kanban";

type OdooControlPanelProps = {
  breadcrumb: string;
  activeView?: PreviewViewTab;
  availableViews?: PreviewViewTab[];
  onViewChange?: (view: PreviewViewTab) => void;
  showSearchPlaceholder?: boolean;
};

const VIEW_LABELS: Record<PreviewViewTab, string> = {
  form: "Form",
  list: "List",
  kanban: "Kanban",
};

export function OdooControlPanel({
  breadcrumb,
  activeView = "form",
  availableViews = ["form"],
  onViewChange,
  showSearchPlaceholder = true,
}: OdooControlPanelProps) {
  return (
    <div className="odoo-control-panel" data-testid="odoo-control-panel">
      <div className="odoo-control-panel-breadcrumb">{breadcrumb}</div>
      <div className="odoo-control-panel-actions">
        {showSearchPlaceholder ? (
          <span className="odoo-control-panel-search" aria-hidden>
            Search… (live in Odoo)
          </span>
        ) : null}
        <span className="odoo-btn-primary">New</span>
        {(availableViews.length > 1 ? availableViews : (["form"] as PreviewViewTab[])).map(
          (view) => (
          <button
            key={view}
            type="button"
            className={view === activeView ? "odoo-btn-primary" : "odoo-btn-secondary"}
            onClick={() => onViewChange?.(view)}
            disabled={!onViewChange || availableViews.length <= 1}
          >
            {VIEW_LABELS[view]}
          </button>
          ),
        )}
      </div>
    </div>
  );
}

export type { PreviewViewTab };
