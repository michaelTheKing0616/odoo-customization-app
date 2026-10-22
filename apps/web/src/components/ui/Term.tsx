"use client";

import * as React from "react";
import { PreviewCard } from "@base-ui/react/preview-card";
import { lookupTerm, odooModelUrl, type TermEntry } from "@/lib/terms";
import { TechName } from "@/components/ui/TechName";

/** Connection's Odoo URL for "Open in Odoo"; pages that know it wrap their content in this. */
export const TermOdooUrl = React.createContext<string | undefined>(undefined);

/**
 * Plain word on screen; hover, focus or tap shows Odoo's own term, the technical name, where it lives,
 * what it means and version differences, with Open in Odoo / Copy technical name.
 * Pass `tech` to look up the glossary, or a full `entry`. Keyboard: Tab to focus opens the card.
 */
export function Term({ tech, entry, children }: { tech?: string; entry?: TermEntry; children?: React.ReactNode }) {
  const t = entry ?? (tech ? lookupTerm(tech) : undefined);
  const base = React.useContext(TermOdooUrl);
  const label = children ?? t?.plain ?? tech;
  if (!t) return <>{label}</>;
  const href = odooModelUrl(base, t.tech);
  return (
    <PreviewCard.Root>
      <PreviewCard.Trigger
        render={<span tabIndex={0} />}
        className="cursor-help underline decoration-dotted decoration-muted underline-offset-[3px]"
        data-testid={`term-${t.tech}`}
      >
        {label}
      </PreviewCard.Trigger>
      <PreviewCard.Portal>
        <PreviewCard.Positioner sideOffset={6}>
          <PreviewCard.Popup className="z-50 max-w-xs rounded-lg border border-border-subtle bg-surface-overlay p-3 text-sm text-ink shadow-raised">
            <p className="text-xs uppercase tracking-[var(--tracking-label)] text-muted">In Odoo{t.app ? ` · ${t.app}` : ""}</p>
            <p className="font-medium">{t.odoo}{t.kind ? <span className="ml-1 font-normal text-muted">({t.kind.toLowerCase()})</span> : null}</p>
            {t.meaning ? <p className="mt-1 text-pretty">{t.meaning}</p> : null}
            <p className="mt-2"><TechName name={t.tech} /></p>
            {t.versions ? <p className="mt-2 text-muted">{t.versions}</p> : null}
            {t.note ? <p className="mt-2 text-muted">{t.note}</p> : null}
            {href ? (
              <p className="mt-2"><a className="text-accent underline-offset-2 hover:underline" href={href} target="_blank" rel="noreferrer">Open in Odoo</a></p>
            ) : null}
          </PreviewCard.Popup>
        </PreviewCard.Positioner>
      </PreviewCard.Portal>
    </PreviewCard.Root>
  );
}
