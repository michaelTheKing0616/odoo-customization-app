"use client";

type StudioMobileTab = "preview" | "chat";

type StudioMobileTabsProps = {
  value: StudioMobileTab;
  onChange: (tab: StudioMobileTab) => void;
};

/** Phone-only switch between the form artifact and the refine thread (hidden ≥768px). */
export function StudioMobileTabs({ value, onChange }: StudioMobileTabsProps) {
  return (
    <div className="studio-mobile-tabs" role="group" aria-label="Show">
      <button
        type="button"
        className={`studio-mobile-tab${value === "preview" ? " is-selected" : ""}`}
        aria-pressed={value === "preview"}
        data-testid="studio-mobile-tab-preview"
        onClick={() => onChange("preview")}
      >
        Form
      </button>
      <button
        type="button"
        className={`studio-mobile-tab${value === "chat" ? " is-selected" : ""}`}
        aria-pressed={value === "chat"}
        data-testid="studio-mobile-tab-refine"
        onClick={() => onChange("chat")}
      >
        Refine
      </button>
    </div>
  );
}
