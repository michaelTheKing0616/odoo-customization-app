"use client";

import { ChevronLeftIcon, ChevronRightIcon, GearIcon } from "./OdooIcons";

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

/** Odoo control panel: New + breadcrumb + gear left, pager (form) or search right. */
export function OdooControlPanel({
  breadcrumb,
  activeView = "form",
  availableViews = ["form"],
  onViewChange,
  showSearchPlaceholder = true,
  showNewButton = true,
}: OdooControlPanelProps) {
  const parts = breadcrumb.split(/\s*[›>/]\s*/).filter(Boolean);
  return (
    <div className="ofp-cp" data-testid="odoo-control-panel">
      <div className="ofp-cp-left">
        {showNewButton ? (
          <button type="button" className="ofp-btn ofp-btn-primary" data-testid="odoo-preview-new" disabled>
            New
          </button>
        ) : null}
        <nav className="ofp-breadcrumb" aria-label="Breadcrumb">
          {parts.map((part, index) => (
            <span key={`${part}-${index}`} className="ofp-breadcrumb-part">
              {index > 0 ? (
                <span className="ofp-breadcrumb-sep" aria-hidden>
                  /
                </span>
              ) : null}
              <span className={index === parts.length - 1 ? "ofp-breadcrumb-current" : "ofp-breadcrumb-link"}>
                {part}
              </span>
            </span>
          ))}
        </nav>
        <span className="ofp-cp-gear" aria-hidden>
          <GearIcon />
        </span>
      </div>
      <div className="ofp-cp-right">
        {activeView === "form" ? (
          <span className="ofp-pager" aria-label="Record 1 of 1">
            <span className="ofp-pager-value">1 / 1</span>
            <span className="ofp-pager-btn" aria-hidden>
              <ChevronLeftIcon />
            </span>
            <span className="ofp-pager-btn" aria-hidden>
              <ChevronRightIcon />
            </span>
          </span>
        ) : showSearchPlaceholder ? (
          <span className="ofp-cp-search" aria-hidden>
            Search...
          </span>
        ) : null}
        {availableViews.length > 1 ? (
          <div className="ofp-switcher" role="group" aria-label="Preview view">
            {availableViews.map((view) => (
              <button
                key={view}
                type="button"
                className={`ofp-switch ${view === activeView ? "is-active" : ""}`}
                aria-pressed={view === activeView}
                onClick={() => onViewChange?.(view)}
                disabled={!onViewChange}
              >
                {VIEW_LABELS[view]}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export type { PreviewViewTab };
