"use client";

import Link from "next/link";

type StudioOpenInOdooProps = {
  goldOptionA: boolean;
  goldCanOpenSettings: boolean;
  goldInspect: { href: string; label: string; hint: string } | null;
  goldHostMessage?: string | null;
  appIsLiveOnOdoo: boolean;
  openInOdooUrl: string | null;
  fieldPack: boolean;
  hostFormName: string;
  liveAppName: string;
  testId?: string;
};

export function StudioOpenInOdoo({
  goldOptionA,
  goldCanOpenSettings,
  goldInspect,
  goldHostMessage,
  appIsLiveOnOdoo,
  openInOdooUrl,
  fieldPack,
  hostFormName,
  liveAppName,
  testId,
}: StudioOpenInOdooProps) {
  if (goldOptionA && goldCanOpenSettings && goldInspect) {
    return (
      <a
        href={goldInspect.href}
        target="_blank"
        rel="noopener noreferrer"
        className="btn btn-secondary"
        data-testid={testId}
        title={goldInspect.hint}
      >
        {goldInspect.label}
      </a>
    );
  }
  if (goldOptionA) {
    return (
      <button
        type="button"
        className="btn btn-secondary"
        disabled
        data-testid={testId}
        title={
          goldHostMessage ||
          "Install Invoicing on this connection, Promote the zip, then open Invoicing → Configuration → Settings. Settings → Currency is the Enterprise tease."
        }
      >
        Open Accounting Settings
      </button>
    );
  }
  if (appIsLiveOnOdoo && openInOdooUrl) {
    return (
      <a
        href={openInOdooUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="btn btn-secondary"
        data-testid={testId}
        title={
          fieldPack
            ? `Opens ${hostFormName} in Odoo — look under the stock app (Sales / Invoicing), not a new app tile.`
            : `Opens ${liveAppName} in Odoo — look on the home grid, not Apps.`
        }
      >
        Open in Odoo
      </a>
    );
  }
  return (
    <button
      type="button"
      className="btn btn-secondary"
      disabled
      data-testid={testId}
      title={
        fieldPack
          ? `Apply or Promote first. Then open ${hostFormName} in Odoo to see the change.`
          : "Apply this app first. The canvas is a preview — Odoo has no new menu until you apply."
      }
    >
      Open in Odoo
    </button>
  );
}

type StudioOpenInViewDesignerProps = {
  href: string;
  designerModel: string | null;
  appIsLiveOnOdoo: boolean;
  fieldPack: boolean;
  hostFormName: string;
  compact?: boolean;
  testId?: string;
};

export function StudioOpenInViewDesigner({
  href,
  designerModel,
  appIsLiveOnOdoo,
  fieldPack,
  hostFormName,
  compact,
  testId,
}: StudioOpenInViewDesignerProps) {
  const title = !designerModel
    ? "Opens View Designer. This draft has no form model yet."
    : appIsLiveOnOdoo
      ? `Edit ${designerModel} views in View Designer`
      : fieldPack
        ? `Opens View Designer on ${hostFormName}. Apply these fields first so they exist in Odoo.`
        : "Opens View Designer. Apply this app first so the form exists in Odoo.";
  return (
    <Link href={href} className="btn btn-secondary" data-testid={testId} title={title}>
      {compact ? "View Designer" : "Open in View Designer"}
    </Link>
  );
}
