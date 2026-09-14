"use client";

import { HostInstallPanel } from "./HostInstallDialog";
import { StudioBusyLabel } from "./StudioBusyLabel";
import type { AuthoringFinding, HostInstallOffer, OptionASettings } from "@/lib/draft-form-preview";

export type GoldHostStatus = {
  host_ready: boolean;
  missing_depends: string[];
  install_module?: string | null;
  install_label?: string | null;
  href?: string | null;
  label?: string;
  message?: string;
  action_id?: number | null;
};

export type GoldInspectLink = {
  href: string;
  label: string;
  hint: string;
};

type StudioOptionAPanelProps = {
  goldOptionA: boolean;
  authoredOptionA: boolean;
  goldId: string;
  goldHonesty: string;
  goldSettings: OptionASettings | null;
  goldHost: GoldHostStatus | null;
  goldInspect: GoldInspectLink | null;
  goldNeedsInvoicing: boolean;
  goldCanPromote: boolean;
  goldCanOpenSettings: boolean;
  goldPromoted: boolean;
  authoringPassed: boolean;
  authoringRetryable: boolean;
  hostInstallOffers: HostInstallOffer[];
  leftoverAuthoringFindings: AuthoringFinding[];
  isOdooOnline: boolean;
  busy: string | null;
  onInstallInvoicing: () => void;
  onDownloadZip: () => void;
  onProveSandbox: () => void;
  onPromote: () => void;
  onRetryAuthoring: () => void;
  onReverify: () => void;
  onInstallHost: (offer: HostInstallOffer, phrase: string) => void;
};

export function StudioOptionAPanel({
  goldOptionA,
  authoredOptionA,
  goldId,
  goldHonesty,
  goldSettings,
  goldHost,
  goldInspect,
  goldNeedsInvoicing,
  goldCanPromote,
  goldCanOpenSettings,
  goldPromoted,
  authoringPassed,
  authoringRetryable,
  hostInstallOffers,
  leftoverAuthoringFindings,
  isOdooOnline,
  busy,
  onInstallInvoicing,
  onDownloadZip,
  onProveSandbox,
  onPromote,
  onRetryAuthoring,
  onReverify,
  onInstallHost,
}: StudioOptionAPanelProps) {
  if (!goldOptionA && !authoredOptionA) return null;

  return (
    <>
      {goldOptionA ? (
        <div className="studio-option-a" data-testid="studio-gold-option-a">
          <p className="studio-option-a-kicker">Option A</p>
          <h3 className="studio-option-a-title">
            Gold{goldId ? ` — ${goldId}` : ""} (not a new app)
          </h3>
          <p className="studio-option-a-body">
            {goldHonesty ||
              "Community has no ECB Service dropdown. This zip adds Central Bank of Nigeria and writes stock res.currency.rate."}{" "}
            <strong>Start new app</strong> if you are still looking at Purchase Requests —
            do not Install this onto that form.
          </p>
          {goldSettings?.fields?.length ? (
            <ul className="studio-finding-list">
              {goldSettings.fields.map((f) => (
                <li key={f.name}>
                  {f.string} <span className="text-muted">({f.name})</span>
                </li>
              ))}
            </ul>
          ) : null}
          <p className="studio-option-a-body">
            Sandbox prove does not install Invoicing on <em>this</em> connection. Settings →
            search Currency → Automatic Currency Rates is Community&apos;s Enterprise upgrade
            tease (no ECB Service). Flow: install Invoicing here if missing → sandbox smoke →{" "}
            <strong>Promote</strong> → Invoicing → Configuration → Settings → Central Bank of
            Nigeria. Not a new app tile. Not Purchase Request Currency.
          </p>
          {goldHost?.host_ready === false ? (
            <p data-testid="studio-gold-host-missing" className="studio-option-a-host">
              {goldHost.message}
            </p>
          ) : null}
          <div className="studio-option-a-actions">
            {goldNeedsInvoicing ? (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={Boolean(busy) || isOdooOnline}
                data-testid="studio-gold-install-invoicing"
                onClick={onInstallInvoicing}
              >
                {busy === "install-host" ? (
                  <StudioBusyLabel>Installing…</StudioBusyLabel>
                ) : (
                  "Install Invoicing on this connection"
                )}
              </button>
            ) : null}
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={Boolean(busy)}
              onClick={onDownloadZip}
            >
              {busy === "zip" ? <StudioBusyLabel>Exporting…</StudioBusyLabel> : "Download module zip"}
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={Boolean(busy) || isOdooOnline}
              title={isOdooOnline ? "Sandbox prove is not available on Odoo Online" : undefined}
              onClick={onProveSandbox}
            >
              {busy === "prove" ? (
                <StudioBusyLabel>Sandbox…</StudioBusyLabel>
              ) : (
                "Sandbox install & smoke"
              )}
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={Boolean(busy) || !goldCanPromote}
              data-testid="studio-gold-promote"
              title={
                isOdooOnline
                  ? "Promote is not available on Odoo Online"
                  : goldCanPromote
                    ? "Install the sandbox-validated zip on this connection (pulls Invoicing if needed)"
                    : "Run Sandbox install & smoke first (validation lasts 2 hours)"
              }
              onClick={onPromote}
            >
              {busy === "promote" ? (
                <StudioBusyLabel>Promoting…</StudioBusyLabel>
              ) : goldPromoted ? (
                "Promote again"
              ) : (
                "Promote to this connection"
              )}
            </button>
            {goldCanOpenSettings && goldInspect ? (
              <a
                href={goldInspect.href}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-secondary btn-sm"
                data-testid="studio-gold-open-odoo"
                title={goldInspect.hint}
              >
                {goldInspect.label}
              </a>
            ) : (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled
                data-testid="studio-gold-open-odoo"
                title={
                  goldHost?.message ||
                  "Promote first. Then Invoicing → Configuration → Settings — not Settings → Currency."
                }
              >
                Open Accounting Settings
              </button>
            )}
          </div>
          <p className="studio-option-a-foot">
            {goldCanOpenSettings && goldInspect
              ? goldInspect.hint
              : goldHost?.message ||
                "Open Accounting Settings stays off until Invoicing is on this connection and you Promote."}
          </p>
        </div>
      ) : null}

      {authoredOptionA ? (
        <div className="studio-option-a" data-testid="studio-authored-option-a">
          <p className="studio-option-a-kicker">Option A</p>
          <h3 className="studio-option-a-title">
            {authoringPassed
              ? "Module — zip and sandbox unlocked"
              : "Module (not a new app)"}
          </h3>
          <p className="studio-option-a-body">
            {goldHonesty ||
              "This extends a stock form (for example Sales) with Python — markup %, WHT on markup only, sales not purchases. Live Install cannot land that code."}{" "}
            {authoringRetryable ? (
              busy === "generate"
                ? "Repairing incomplete JSON automatically — diagnosis stays locked."
                : "Authoring did not finish, so zip stayed locked. Retry authoring if this is still here after a moment. Do not click Install this app."
            ) : (
              <>
                Download the zip after the authoring gate passes, sandbox-prove, then{" "}
                <strong>Promote</strong>. Do not click Install this app.
              </>
            )}
          </p>
          {hostInstallOffers.length > 0 ? (
            <HostInstallPanel
              offers={hostInstallOffers}
              busy={busy === "install-host" || busy === "reverify"}
              disabled={Boolean(busy) || isOdooOnline}
              disabledReason={
                isOdooOnline
                  ? "Odoo Online cannot install Community apps from here"
                  : undefined
              }
              onInstall={onInstallHost}
            />
          ) : null}
          {leftoverAuthoringFindings.length > 0 ? (
            <ul className="studio-finding-list">
              {leftoverAuthoringFindings.slice(0, 8).map((row, i) => (
                <li key={`auth-${i}`}>
                  {row.code ? `${row.code}: ` : ""}
                  {row.message}
                  {row.file ? ` (${row.file})` : ""}
                </li>
              ))}
            </ul>
          ) : null}
          <div className="studio-option-a-actions">
            {authoringRetryable ? (
              <button
                type="button"
                className="btn btn-brand btn-sm"
                disabled={Boolean(busy)}
                data-testid="studio-retry-authoring"
                onClick={onRetryAuthoring}
              >
                {busy === "generate" ? (
                  <StudioBusyLabel>Repairing…</StudioBusyLabel>
                ) : (
                  "Retry authoring"
                )}
              </button>
            ) : null}
            {!authoringPassed && !authoringRetryable ? (
              <button
                type="button"
                className="btn btn-brand btn-sm"
                disabled={Boolean(busy)}
                data-testid="studio-reverify-authoring"
                onClick={onReverify}
              >
                {busy === "reverify" ? (
                  <StudioBusyLabel>Re-checking…</StudioBusyLabel>
                ) : (
                  "Re-check authoring gate"
                )}
              </button>
            ) : null}
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={Boolean(busy) || !authoringPassed}
              title={
                authoringPassed
                  ? undefined
                  : "Authoring gate has not passed — zip stays locked"
              }
              onClick={onDownloadZip}
            >
              {busy === "zip" ? <StudioBusyLabel>Exporting…</StudioBusyLabel> : "Download module zip"}
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={Boolean(busy) || isOdooOnline || !authoringPassed}
              title={
                isOdooOnline
                  ? "Sandbox prove is not available on Odoo Online"
                  : authoringPassed
                    ? undefined
                    : "Authoring gate has not passed — sandbox stays locked"
              }
              onClick={onProveSandbox}
            >
              {busy === "prove" ? (
                <StudioBusyLabel>Sandbox…</StudioBusyLabel>
              ) : (
                "Sandbox install & smoke"
              )}
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={Boolean(busy) || !goldCanPromote}
              title={
                isOdooOnline
                  ? "Promote is not available on Odoo Online"
                  : goldCanPromote
                    ? "Install the sandbox-validated zip on this connection"
                    : "Run Sandbox install & smoke first (validation lasts 2 hours)"
              }
              onClick={onPromote}
            >
              {busy === "promote" ? (
                <StudioBusyLabel>Promoting…</StudioBusyLabel>
              ) : goldPromoted ? (
                "Promote again"
              ) : (
                "Promote to this connection"
              )}
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
