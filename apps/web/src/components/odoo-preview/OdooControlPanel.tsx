"use client";

type PreviewViewTab = "form" | "list" | "kanban";

type OdooControlPanelProps = {
  breadcrumb: string;
  activeView?: PreviewViewTab;
  availableViews?: PreviewViewTab[];
  onViewChange?: (view: PreviewViewTab) => void;
  showSearchPlaceholder?: boolean;
  showNewButton?: boolean;
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
  showNewButton = true,
}: OdooControlPanelProps) {
  return (
    <div className="odoo-control-panel" data-testid="odoo-control-panel">
      <nav className="odoo-control-panel-breadcrumb" aria-label="Breadcrumb">
        {breadcrumb.split(/\s*[›>/]\s*/).filter(Boolean).map((part, index, all) => (
          <span key={`${part}-${index}`} className="odoo-breadcrumb-part">
            {index > 0 ? <span className="odoo-breadcrumb-sep" aria-hidden> / </span> : null}
            <span className={index === all.length - 1 ? "odoo-breadcrumb-current" : undefined}>
              {part}
            </span>
          </span>
        ))}
      </nav>
      <div className="odoo-control-panel-actions">
        {showSearchPlaceholder ? (
          <span className="odoo-control-panel-search" aria-hidden>
            Search… (live in Odoo)
          </span>
        ) : null}
        {showNewButton ? (
          <button type="button" className="odoo-btn-primary" data-testid="odoo-preview-new" disabled>
            New
          </button>
        ) : null}
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
