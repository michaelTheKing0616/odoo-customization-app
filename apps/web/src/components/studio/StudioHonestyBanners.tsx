"use client";

import Link from "next/link";
import { Callout } from "@/components/ui/Callout";
import type { DocumentGrammarCard, StockAppRow, SurfaceFinding } from "@/lib/draft-form-preview";
import type { DraftBanner } from "@/lib/draft-studio-banners";
import type { FormSlotOption, InheritPlacementRow } from "@/lib/draft-models";
import type { OperatorSurface } from "@/lib/operator-surface";
import { StudioBusyLabel } from "./StudioBusyLabel";

type StudioHonestyBannersProps = {
  connectionId: string;
  applyNote: string | null;
  calloutTitle: string;
  odooAppUrl: string | null;
  goldInspectHref?: string | null;
  goldInspectLabel?: string | null;
  artifactConsistent: boolean;
  appIsLiveOnOdoo: boolean;
  stockReuse: boolean;
  refuseClone: boolean;
  goldOptionA: boolean;
  authoredOptionA: boolean;
  fieldPack: boolean;
  hostFormName: string;
  liveAppName: string;
  grammarCard: DocumentGrammarCard | null;
  surfaceFindings: SurfaceFinding[];
  liveApplyBanner: DraftBanner | null;
  unfinishedBanner: DraftBanner | null;
  operatorSurface: OperatorSurface | null;
  placementRows: InheritPlacementRow[];
  slotCatalog: FormSlotOption[];
  stockApps: StockAppRow[];
  applyBlocked: string | null;
  refineBusy: boolean;
  onPlaceField: (fieldLabel: string, phrase: string) => void;
  onRepairExpert?: () => void;
  /** Studio Contract scorecard — model-agnostic Apply gate */
  contractScorecard?: {
    pass?: boolean;
    blocking?: boolean;
    summary?: string | null;
    repairs?: string[];
  } | null;
};

export function StudioHonestyBanners({
  connectionId,
  applyNote,
  calloutTitle,
  odooAppUrl,
  goldInspectHref,
  goldInspectLabel,
  artifactConsistent,
  appIsLiveOnOdoo,
  stockReuse,
  refuseClone,
  goldOptionA,
  authoredOptionA,
  fieldPack,
  hostFormName,
  liveAppName,
  grammarCard,
  surfaceFindings,
  liveApplyBanner,
  unfinishedBanner,
  operatorSurface,
  placementRows,
  slotCatalog,
  stockApps,
  applyBlocked,
  refineBusy,
  onPlaceField,
  onRepairExpert,
  contractScorecard,
}: StudioHonestyBannersProps) {
  const hideGrammar =
    stockReuse || refuseClone || goldOptionA || authoredOptionA;
  const optionAModule = goldOptionA || authoredOptionA;
  const showPreviewOnly =
    !appIsLiveOnOdoo && !stockReuse && !refuseClone && !optionAModule;
  const showSlots =
    fieldPack &&
    placementRows.length > 0 &&
    slotCatalog.length > 0 &&
    !optionAModule;
  const operatorSurfaceCopy =
    optionAModule &&
    (!operatorSurface?.summary || /residual app/i.test(operatorSurface.summary))
      ? `«${liveAppName}» extends ${hostFormName} via an Option A module — zip → sandbox → Promote. Not a new Apps tile. Do not click Install this app.`
      : operatorSurface?.summary;

  return (
    <div className="studio-banner-stack">
      {contractScorecard?.blocking ? (
        <Callout
          variant="warning"
          title="Studio contract not met"
          testId="studio-contract-blocker"
          actions={
            onRepairExpert ? (
              <button
                type="button"
                className="text-sm font-medium text-accent"
                onClick={onRepairExpert}
                disabled={refineBusy}
              >
                {refineBusy ? <StudioBusyLabel /> : "Repair with Expert"}
              </button>
            ) : null
          }
        >
          {contractScorecard.summary
            ? `Expected: ${contractScorecard.summary}. `
            : ""}
          {(contractScorecard.repairs || []).slice(0, 3).join(" · ") ||
            "Fix placement or missing workflow surfaces before Apply."}
        </Callout>
      ) : contractScorecard?.pass && contractScorecard.summary ? (
        <Callout
          variant="info"
          title="Studio contract"
          testId="studio-contract-summary"
          className="studio-callout-success-tone"
        >
          {contractScorecard.summary}
        </Callout>
      ) : null}
      {applyNote ? (
        <Callout
          variant="info"
          title={calloutTitle}
          className="studio-callout-success-tone"
          testId="studio-apply-note"
          actions={
            odooAppUrl ? (
              <a
                href={odooAppUrl}
                target="_blank"
                rel="noreferrer"
                data-testid="open-app-in-odoo"
                className="text-sm font-medium text-accent"
              >
                Open in Odoo
              </a>
            ) : goldInspectHref && goldInspectLabel ? (
              <a
                href={goldInspectHref}
                target="_blank"
                rel="noreferrer"
                data-testid="open-app-in-odoo"
                className="text-sm font-medium text-accent"
              >
                {goldInspectLabel}
              </a>
            ) : null
          }
        >
          {applyNote}
        </Callout>
      ) : null}

      {!artifactConsistent ? (
        <Callout variant="warning" title="Session resume notice">
          Artifact hash differs from the last saved turn — reload or refine to reconcile.
        </Callout>
      ) : null}

      {showPreviewOnly ? (
        <Callout variant="info" title="Preview only — not in Odoo yet">
          {fieldPack ? (
            <>
              This canvas shows extra fields on <strong>{hostFormName}</strong>. Click{" "}
              <strong>Apply these fields</strong> to add them on the form people already
              use. It does not create a new app tile.
            </>
          ) : (
            <>
              This canvas is a draft. Click <strong>Install this app</strong> to create the{" "}
              <strong>{liveAppName}</strong> tile on the Odoo home grid (not Apps).
              {liveAppName.toLowerCase() === "helpdesk"
                ? " Tickets is a submenu inside Helpdesk — it will not appear as its own Apps tile."
                : ""}
            </>
          )}
        </Callout>
      ) : null}

      {grammarCard && !hideGrammar ? (
        <Callout variant="info" title="What will exist in Odoo" testId="studio-grammar-card">
          {grammarCard.summary}
        </Callout>
      ) : null}

      {operatorSurfaceCopy ? (
        <Callout variant="info" title="Where operators will find it" testId="studio-operator-surface">
          {operatorSurfaceCopy}
        </Callout>
      ) : null}

      {showSlots ? (
        <Callout
          variant="info"
          title={`Where on ${hostFormName}`}
          testId="studio-form-slots"
        >
          <p className="m-0 mb-2">
            Fields sit next to vendor or dates, on Other Info, or on a named tab — not in a
            nested Extension group. View Designer can still move them after Apply.
          </p>
          <div className="studio-form-slots">
            {placementRows.map((row) => (
              <label key={row.name} className="studio-form-slot-row">
                <span>{row.string}</span>
                <select
                  className="input"
                  value={row.slot}
                  disabled={refineBusy}
                  aria-label={`Place ${row.string}`}
                  onChange={(event) => {
                    const next = slotCatalog.find((item) => item.id === event.target.value);
                    if (!next || next.id === row.slot) return;
                    onPlaceField(row.string, next.phrase);
                  }}
                >
                  {slotCatalog.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
        </Callout>
      ) : null}

      {surfaceFindings.length ? (
        <Callout variant="warning" title="Not ready to install" testId="studio-surface-gate">
          <p className="m-0">
            This draft would look amateur in Odoo. Install is off until the document grammar
            is unique (no duplicate notebooks, no placeholder name, money and approval slots
            filled).
          </p>
          <ul className="studio-finding-list">
            {surfaceFindings.map((row, i) => (
              <li key={`${row.element || "f"}-${i}`}>{row.detail}</li>
            ))}
          </ul>
          {onRepairExpert ? (
            <div className="mt-2">
              <button
                type="button"
                className="btn btn-secondary"
                data-testid="studio-surface-repair-expert"
                disabled={refineBusy}
                onClick={onRepairExpert}
              >
                {refineBusy ? <StudioBusyLabel>Repairing…</StudioBusyLabel> : "Repair with Expert"}
              </button>
            </div>
          ) : null}
        </Callout>
      ) : null}

      {liveApplyBanner ? (
        <Callout variant="warning" title={liveApplyBanner.title} testId={liveApplyBanner.testId}>
          {liveApplyBanner.body}
        </Callout>
      ) : null}

      {unfinishedBanner ? (
        <Callout variant="warning" title={unfinishedBanner.title} testId={unfinishedBanner.testId}>
          {unfinishedBanner.body}
        </Callout>
      ) : null}

      {stockReuse ? (
        <Callout
          variant="info"
          title="Stock Community apps — no custom form"
          testId="studio-stock-reuse"
        >
          <p className="m-0">
            This draft has no x_* document to preview. Stock Purchase is RFQs and vendor POs,
            not staff purchase requests with manager approval. If you wanted that form, start
            a new app and keep <strong>One simple document</strong> — do not pick stock-only.
          </p>
          {stockApps.length ? (
            <ul className="studio-finding-list">
              {stockApps.map((app) => (
                <li key={app.id}>
                  {app.label}{" "}
                  <span className="text-muted">({app.id})</span>
                </li>
              ))}
            </ul>
          ) : null}
          <p className="mt-2 mb-0">
            <Link href={`/connections/${connectionId}/job`} className="text-accent">
              Open Job Autopilot
            </Link>{" "}
            for sandbox install of named stock apps.
          </p>
        </Callout>
      ) : null}

      {applyBlocked ? (
        <Callout variant="warning" title="Apply blocked on this connection">
          {applyBlocked}
        </Callout>
      ) : null}

      {refineBusy ? (
        <p className="studio-inline-wait">
          <StudioBusyLabel>Updating preview</StudioBusyLabel>
        </p>
      ) : null}
    </div>
  );
}
