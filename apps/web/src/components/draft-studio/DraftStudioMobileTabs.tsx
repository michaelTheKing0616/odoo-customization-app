"use client";

export type DraftStudioMobileTab = "preview" | "chrome";

type DraftStudioMobileTabsProps = {
  value: DraftStudioMobileTab;
  onChange: (tab: DraftStudioMobileTab) => void;
};

/**
 * Phone-only switch (hidden at 768px and up) between the form preview and the
 * scorecard, so Completeness, Certification, and Autopilot stay reachable on a phone.
 */
export function DraftStudioMobileTabs({ value, onChange }: DraftStudioMobileTabsProps) {
  return (
    <div
      className="studio-mobile-tabs draft-studio-mobile-tabs"
      role="group"
      aria-label="Show"
      data-testid="draft-studio-mobile-tabs"
    >
      <button
        type="button"
        className={`studio-mobile-tab${value === "preview" ? " is-selected" : ""}`}
        aria-pressed={value === "preview"}
        data-testid="draft-studio-mobile-tab-preview"
        onClick={() => onChange("preview")}
      >
        Preview
      </button>
      <button
        type="button"
        className={`studio-mobile-tab${value === "chrome" ? " is-selected" : ""}`}
        aria-pressed={value === "chrome"}
        data-testid="draft-studio-mobile-tab-scorecard"
        onClick={() => onChange("chrome")}
      >
        Scorecard
      </button>
    </div>
  );
}
