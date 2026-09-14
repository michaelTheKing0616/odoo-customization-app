"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DialogPanel } from "@/components/ui/Dialog";
import { Package } from "@/components/ui/icons";
import type { HostInstallOffer } from "@/lib/draft-form-preview";

const DEFAULT_PHRASE = "I understand the risks";

type HostInstallPanelProps = {
  offers: HostInstallOffer[];
  busy?: boolean;
  disabled?: boolean;
  disabledReason?: string;
  autoOpen?: boolean;
  phrase?: string;
  onInstall: (offer: HostInstallOffer, phrase: string) => void;
};

export function HostInstallPanel({
  offers,
  busy = false,
  disabled = false,
  disabledReason,
  autoOpen = true,
  phrase = DEFAULT_PHRASE,
  onInstall,
}: HostInstallPanelProps) {
  const [active, setActive] = useState<HostInstallOffer | null>(null);
  const [typed, setTyped] = useState("");
  const [openedKey, setOpenedKey] = useState("");

  const offerKey = offers.map((o) => o.module).join("|");

  useEffect(() => {
    if (!autoOpen || disabled || !offers.length) return;
    if (openedKey === offerKey) return;
    setOpenedKey(offerKey);
    setActive(offers[0] ?? null);
  }, [autoOpen, disabled, offerKey, openedKey, offers]);

  useEffect(() => {
    if (active) setTyped("");
  }, [active]);

  if (!offers.length) return null;

  const canConfirm = Boolean(active) && typed === phrase && !busy && !disabled;

  return (
    <>
      <div className="mt-3 space-y-2.5" data-testid="studio-host-install">
        {offers.map((offer) => (
          <div
            key={offer.module}
            className="flex flex-wrap items-start gap-3 rounded-lg border border-accent/30 bg-accent/5 px-3.5 py-3"
            data-testid={`studio-host-install-${offer.module}`}
          >
            <div
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent/15 text-accent"
              aria-hidden
            >
              <Package className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="m-0 font-semibold text-ink">{offer.label} is not on this connection</p>
              <p className="mt-1 text-[13px] leading-snug text-muted">
                Needed so this Option A module can inherit{" "}
                {offer.models.map((model) => (
                  <Badge key={model} variant="lock" className="mx-0.5 font-mono">
                    {model}
                  </Badge>
                ))}
                . Installing {offer.label} does not install this custom zip.
              </p>
            </div>
            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={disabled || busy}
              title={disabledReason}
              data-testid={`studio-host-install-open-${offer.module}`}
              onClick={() => setActive(offer)}
            >
              {busy && active?.module === offer.module ? "Installing…" : `Install ${offer.label}`}
            </Button>
          </div>
        ))}
      </div>

      <DialogPanel
        open={Boolean(active)}
        onOpenChange={(open) => {
          if (!open && !busy) setActive(null);
        }}
        title={active ? `Install ${active.label} on this connection` : "Install stock app"}
        description="Stock Community app — not your Option A zip. Completeness ≠ Cert. Promote stays human."
        testId="studio-host-install-dialog"
        className="max-w-xl"
        footer={
          <>
            <Button
              type="button"
              variant="secondary"
              size="md"
              disabled={busy}
              data-testid="studio-host-install-cancel"
              onClick={() => setActive(null)}
            >
              Not now
            </Button>
            <Button
              type="button"
              variant="primary"
              size="md"
              disabled={!canConfirm}
              loading={busy}
              data-testid="studio-host-install-confirm"
              onClick={() => {
                if (!active || !canConfirm) return;
                onInstall(active, phrase);
              }}
            >
              {active ? `Install ${active.label}` : "Install"}
            </Button>
          </>
        }
      >
        {active ? (
          <div className="space-y-4">
            {disabledReason ? (
              <p className="rounded-md border border-warning/30 bg-warning-subtle px-3 py-2 text-sm text-ink">
                {disabledReason}
              </p>
            ) : null}
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted">Missing on this Odoo</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {active.models.map((model) => (
                  <Badge key={model} variant="lock" className="font-mono">
                    {model}
                  </Badge>
                ))}
              </div>
            </div>
            <p className="text-sm text-ink">
              {active.message ||
                `Those models live in the stock ${active.label} app (${active.module}). This connection does not have them yet, so the authoring gate cannot inherit the host form.`}
            </p>
            <ol className="space-y-2 rounded-md border border-border-subtle bg-surface-muted px-4 py-3 text-sm text-ink">
              <li>
                <span className="font-medium">1. Install {active.label}</span>
                <span className="text-muted">
                  {" "}
                  — stock <code className="font-mono">{active.module}</code>, plus its Community depends.
                </span>
              </li>
              <li>
                <span className="font-medium">2. Re-check the authoring gate</span>
                <span className="text-muted"> — no LLM rewrite; zip stays locked until it passes.</span>
              </li>
              <li>
                <span className="font-medium">3. Zip → sandbox → Promote</span>
                <span className="text-muted"> — do not click Install this app. Promote stays human.</span>
              </li>
            </ol>
            <label className="block text-sm">
              <span className="text-muted">
                Type <code className="font-mono text-accent">{phrase}</code> to continue
              </span>
              <input
                data-testid="studio-host-install-phrase"
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                disabled={busy || disabled}
                autoFocus
                className="mt-1 w-full rounded-md border border-border-subtle bg-surface px-3 py-2 text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
              />
            </label>
          </div>
        ) : null}
      </DialogPanel>
    </>
  );
}
