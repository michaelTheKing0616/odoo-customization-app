"use client";

import { StudioBusyLabel } from "./StudioBusyLabel";
import { StudioOpenInOdoo, StudioOpenInViewDesigner } from "./StudioOpenLinks";

type StudioApplyBarProps = {
  designerHref: string;
  designerModel: string | null;
  appIsLiveOnOdoo: boolean;
  fieldPack: boolean;
  hostFormName: string;
  liveAppName: string;
  goldOptionA: boolean;
  authoredOptionA: boolean;
  goldCanOpenSettings: boolean;
  goldInspect: { href: string; label: string; hint: string } | null;
  goldHostMessage?: string | null;
  openInOdooUrl: string | null;
  canApply: boolean;
  stockReuse: boolean;
  refuseClone: boolean;
  surfaceBlocked: boolean;
  applyBlocked: string | null;
  busy: string | null;
  onApply: () => void;
};

export function StudioApplyBar({
  designerHref,
  designerModel,
  appIsLiveOnOdoo,
  fieldPack,
  hostFormName,
  liveAppName,
  goldOptionA,
  authoredOptionA,
  goldCanOpenSettings,
  goldInspect,
  goldHostMessage,
  openInOdooUrl,
  canApply,
  stockReuse,
  refuseClone,
  surfaceBlocked,
  applyBlocked,
  busy,
  onApply,
}: StudioApplyBarProps) {
  return (
    <>
      <StudioOpenInViewDesigner
        href={designerHref}
        designerModel={designerModel}
        appIsLiveOnOdoo={appIsLiveOnOdoo}
        fieldPack={fieldPack}
        hostFormName={hostFormName}
        testId="open-view-designer"
      />
      <StudioOpenInOdoo
        goldOptionA={goldOptionA}
        goldCanOpenSettings={goldCanOpenSettings}
        goldInspect={goldInspect}
        goldHostMessage={goldHostMessage}
        appIsLiveOnOdoo={appIsLiveOnOdoo}
        openInOdooUrl={openInOdooUrl}
        fieldPack={fieldPack}
        hostFormName={hostFormName}
        liveAppName={liveAppName}
        testId="open-in-odoo"
      />
      <button
        type="button"
        className="btn btn-primary"
        disabled={
          !canApply ||
          stockReuse ||
          refuseClone ||
          goldOptionA ||
          authoredOptionA ||
          surfaceBlocked ||
          busy === "apply"
        }
        title={
          goldOptionA
            ? "Option A gold — zip → sandbox → Promote. Live Install cannot land CBN Python or cron."
            : authoredOptionA
              ? "Option A module — zip → sandbox → Promote. Live Install cannot land markup/WHT Python."
              : stockReuse
                ? "Empty stock-reuse spec — use Job Autopilot, not Install."
                : surfaceBlocked
                  ? "Document grammar is not unique yet — Install is off."
                  : (applyBlocked ?? undefined)
        }
        onClick={onApply}
      >
        {busy === "apply" ? (
          <StudioBusyLabel>Applying…</StudioBusyLabel>
        ) : fieldPack ? (
          "Apply these fields"
        ) : (
          "Install this app"
        )}
      </button>
    </>
  );
}
