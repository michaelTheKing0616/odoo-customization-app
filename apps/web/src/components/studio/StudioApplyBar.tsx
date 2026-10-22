"use client";

import { useState } from "react";
import { api } from "@/lib/api";
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
  /** Stock Odoo apps the design needs that aren't installed yet: step 1 before Install this app. */
  appsToInstall?: { module: string; app: string }[];
  connectionId?: string;
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
  appsToInstall = [],
  connectionId,
}: StudioApplyBarProps) {
  const [installed, setInstalled] = useState<Set<string>>(new Set());
  const [installing, setInstalling] = useState<string | null>(null);
  const [installError, setInstallError] = useState<string | null>(null);
  const pending = appsToInstall.filter((a) => !installed.has(a.module));
  const installApps = async () => {
    if (!connectionId) return;
    setInstallError(null);
    for (const a of pending) {
      setInstalling(a.app);
      try {
        const r = await api.installCommunityModule(connectionId, a.module);
        if (!r.ok) throw new Error(r.message || `${a.app} did not install.`);
        setInstalled((prev) => new Set(prev).add(a.module));
      } catch (e) {
        setInstallError(`${a.app}: ${e instanceof Error ? e.message : "install failed"}`);
        break;
      }
    }
    setInstalling(null);
  };
  const needsApps = pending.length > 0 && !fieldPack;
  const disabled =
    !canApply ||
    needsApps ||
    stockReuse ||
    refuseClone ||
    goldOptionA ||
    authoredOptionA ||
    surfaceBlocked ||
    busy === "apply";
  const blockedReason = goldOptionA
    ? "Custom code ships as a module: download the zip, prove it in a test copy, then publish. Live Install cannot land CBN Python or cron."
    : authoredOptionA
      ? "Custom code: download the zip, prove it in a test copy, then publish. Live Install cannot land markup/WHT Python."
      : stockReuse
        ? "Empty stock-reuse spec. Use Job Autopilot, not Install."
        : surfaceBlocked
          ? "Install is off until the form layout is clean (see Not ready to install above)."
          : needsApps
            ? `Install the Odoo apps this design builds on first (step 1).`
            : (applyBlocked ?? null);
  const showReason = disabled && busy !== "apply" && Boolean(blockedReason);

  return (
    <>
      {appsToInstall.length && !fieldPack ? (
        <div className="studio-install-step" data-testid="studio-install-step" role="group" aria-label="Step 1: install the Odoo apps this design needs">
          <span>{pending.length ? "Step 1. This design builds on:" : "Step 1 done. Installed:"}</span>
          <ul>{appsToInstall.map((a) => <li key={a.module} className="badge">{a.app}{installed.has(a.module) ? " ✓" : ""}</li>)}</ul>
          {pending.length ? (
            <button type="button" className="btn btn-secondary" data-testid="studio-install-apps" disabled={!connectionId || installing !== null} onClick={() => void installApps()}>
              {installing ? <StudioBusyLabel>Installing {installing}…</StudioBusyLabel> : `Install ${pending.length === 1 ? pending[0].app : `${pending.length} apps`}`}
            </button>
          ) : null}
          {installError ? <p className="review-footer-note" role="alert">{installError}</p> : null}
        </div>
      ) : null}
      {showReason ? (
        <p className="review-footer-note" id="studio-apply-reason" data-testid="studio-apply-reason">
          {blockedReason}
        </p>
      ) : null}
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
        data-testid="studio-apply"
        disabled={disabled}
        title={blockedReason ?? undefined}
        aria-describedby={showReason ? "studio-apply-reason" : undefined}
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
