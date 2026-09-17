"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import {
  apiKeyGuideSteps,
  shouldEmphasizeApiKeyGuide,
} from "@/lib/connect-checklist";
import type { HostingKind } from "@/lib/odoo-hosting";
import {
  odooApiKeyDocsUrl,
  odooApiKeyGuideUrl,
} from "@/lib/odoo-hosting";
import { cn } from "@/lib/cn";

type Props = {
  url: string;
  hosting: HostingKind;
  /** Surface after a failed probe/save. */
  errorMessage?: string | null;
  className?: string;
};

/**
 * Walks the user through creating an Odoo API key.
 * Creation happens on Odoo; Ingenium opens the client and collects the pasted key.
 */
export function ConnectApiKeyGuide({ url, hosting, errorMessage, className }: Props) {
  const emphasize = shouldEmphasizeApiKeyGuide(hosting, errorMessage);
  const [open, setOpen] = useState(emphasize);
  useEffect(() => {
    if (emphasize) setOpen(true);
  }, [emphasize]);
  const steps = useMemo(() => apiKeyGuideSteps(hosting), [hosting]);
  const openUrl = odooApiKeyGuideUrl(url);
  const docsUrl = odooApiKeyDocsUrl();

  function openInOdoo() {
    if (!openUrl || typeof window === "undefined") return;
    window.open(openUrl, "_blank", "noopener,noreferrer");
    setOpen(true);
  }

  return (
    <div
      className={cn(
        "rounded-lg border p-4",
        emphasize
          ? "border-warning/40 bg-warning/5"
          : "border-border bg-surface",
        className,
      )}
      data-testid="connect-api-key-guide"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-ink">
            {hosting === "online"
              ? "Create an Odoo API key (recommended for Online)"
              : "Create an Odoo API key (optional but safer)"}
          </h3>
          <p className="mt-1 text-xs text-muted">
            This is an <span className="font-medium text-ink">Odoo external RPC</span> API key
            (XML-RPC / JSON-RPC) so Ingenium can talk to your database —{" "}
            <span className="font-medium text-ink">not</span> a Cursor MCP server key or Model
            Context Protocol connector. The key is created{" "}
            <span className="font-medium text-ink">inside Odoo</span>; Ingenium cannot mint it.
            We open Odoo for you; you paste the key back here.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={!openUrl}
            onClick={openInOdoo}
            data-testid="connect-open-odoo-api-key"
          >
            Open Odoo to create key
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setOpen((v) => !v)}
            data-testid="connect-api-key-guide-toggle"
          >
            {open ? "Hide steps" : "Show steps"}
          </Button>
        </div>
      </div>

      {!openUrl ? (
        <p className="mt-2 text-xs text-muted">
          Enter a valid Odoo URL first — then this button opens that instance.
        </p>
      ) : null}

      {open ? (
        <ol className="mt-3 space-y-2">
          {steps.map((step, i) => (
            <li
              key={step.title}
              className="flex gap-3 rounded-md border border-border/80 bg-surface px-3 py-2 text-sm"
              data-testid={`connect-api-key-step-${i + 1}`}
            >
              <span
                className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent/15 text-[11px] font-semibold text-accent"
                aria-hidden
              >
                {i + 1}
              </span>
              <div className="min-w-0">
                <p className="font-medium text-ink">{step.title}</p>
                <p className="mt-0.5 text-xs text-muted">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      ) : null}

      {emphasize && errorMessage ? (
        <Callout
          variant="warning"
          title="Auth failed — try an API key"
          className="mt-3"
          testId="connect-api-key-auth-nudge"
        >
          Paste the new Odoo RPC API key into the secret field above (not a Cursor MCP key; leave the website password out), then save again.
        </Callout>
      ) : null}

      <p className="mt-3 text-xs text-muted">
        Official reference:{" "}
        <a
          href={docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent underline-offset-2 hover:underline"
        >
          Odoo External API — API keys
        </a>
        .
      </p>
    </div>
  );
}
