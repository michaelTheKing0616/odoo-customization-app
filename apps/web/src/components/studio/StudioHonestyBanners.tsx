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
  /** Studio Contract scorecard: model-agnostic Apply gate */
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
      ? `«${liveAppName}» extends ${hostFormName} via a custom-code module: download the zip, prove it in a sandbox, then publish. Not a new Apps tile. Do not click Install this app.`
      : operatorSurface?.summary;

  return (
    <div className="studio-banner-stack">
      {contractScorecard?.blocking ? (
        <Callout
          variant="warning"
          title="Install is blocked until these checks pass"
          testId="studio-contract-blocker"
          actions={
            onRepairExpert ? (
              <button
                type="button"
                className="text-sm font-medium text-accent"
                data-testid="studio-contract-repair-expert"
                onClick={onRepairExpert}
                disabled={refineBusy}
              >
                {refineBusy ? <StudioBusyLabel>Repairing…</StudioBusyLabel> : "Repair with Expert"}
              </button>
            ) : null
          }
        >
          <p className="text-sm">
            {contractScorecard.summary
              ? `Expected: ${contractScorecard.summary}. `
              : ""}
            Apply and Install stay blocked until these checks pass: no duplicate links
            (M2O), no placeholder satellite stamps, Checklist and Parts lines present (O2M),
            a real Sign-off, and honest custom-code delivery. A complete draft is not
            certified, and neither means Autopilot-ready (A complete draft is not the same as certified, and neither means Autopilot-ready).
          </p>
          {(contractScorecard.repairs || []).length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm" data-testid="studio-contract-repairs">
              {(contractScorecard.repairs || []).slice(0, 5).map((r, i) => (
                <li key={`repair-${i}`}>{r}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm">
              Fix placement or missing workflow surfaces before Apply.
            </p>
          )}
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
          This draft differs from the last saved turn. Reload the page or send a refinement to
          bring them back in line.
        </Callout>
      ) : null}

      {showPreviewOnly || (grammarCard && !hideGrammar) ? (
        <div className="studio-preview-line" role="note" data-testid="studio-preview-line">
          <svg className="studio-preview-line-icon" width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden focusable="false">
            <circle cx="8" cy="8" r="6.25" stroke="currentColor" strokeWidth="1.3" />
            <path d="M8 7.25v4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            <circle cx="8" cy="5" r="0.8" fill="currentColor" />
          </svg>
          {showPreviewOnly ? (
            <span data-testid="studio-preview-only">
              {fieldPack ? (
                <>
                  Preview only. Nothing changes on {hostFormName} until you click{" "}
                  <strong>Apply these fields</strong>.
                </>
              ) : (
                <>
                  Preview only. Nothing changes in Odoo until you click <strong>Install this app</strong>.
                  {liveAppName.toLowerCase() === "helpdesk"
                    ? " Tickets is a submenu inside Helpdesk, so it will not appear as its own Apps tile."
                    : ""}
                </>
              )}
            </span>
          ) : null}
          {grammarCard && !hideGrammar ? (
            <details className="studio-preview-line-more" data-testid="studio-grammar-card">
              <summary>What will exist</summary>
              <span>
                {grammarCard.summary}
                {showPreviewOnly && !fieldPack ? ` It appears as the ${liveAppName} tile on the Odoo home grid.` : ""}
              </span>
            </details>
          ) : null}
        </div>
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
            Fields sit next to vendor or dates, on Other Info, or on a named tab, never in a
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
            Install is off until the form layout is clean in Odoo: no duplicate notebooks, no
            placeholder name, and money and approval fields filled in.
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
          title="Stock Community apps, no custom form"
          testId="studio-stock-reuse"
        >
          <p className="m-0">
            This draft has no x_* document to preview. Stock Purchase is RFQs and vendor POs,
            not staff purchase requests with manager approval. If you wanted that form, start
            a new app and keep <strong>One simple document</strong>. Do not pick stock-only.
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
        <p className="studio-inline-wait" role="status">
          <StudioBusyLabel>Updating the preview…</StudioBusyLabel>
        </p>
      ) : null}
    </div>
  );
}
