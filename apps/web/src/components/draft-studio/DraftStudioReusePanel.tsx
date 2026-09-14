"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { ReuseModelRow } from "@/lib/api";
import type { ReuseDecisionChip } from "@/lib/reuse-chips";

const REUSE_SUGGESTIONS = [
  "res.partner",
  "res.users",
  "product.product",
  "sale.order",
  "account.move",
  "hr.employee",
];

type DraftStudioReusePanelProps = {
  reuseModels: string[];
  reuseCatalog: ReuseModelRow[];
  reuseCatalogByModel: Map<string, ReuseModelRow>;
  filteredReuseCatalog: ReuseModelRow[];
  reuseSearch: string;
  reuseCatalogStatus: "loading" | "ready" | "error";
  reuseCatalogError: string | null;
  autoWiredReuse: ReuseDecisionChip[];
  inferredReuseSuggestions: ReuseDecisionChip[];
  installableReuseSuggestions: ReuseDecisionChip[];
  aiBusy: boolean;
  aiBusyLabel: string | null;
  onToggleReuse: (model: string) => void;
  onSearch: (value: string) => void;
  onReloadCatalog: () => void;
  onConfirmInferred: (model: string) => void;
  onRejectInferred: (model: string) => void;
  onConfirmInstallable: (model: string) => void;
  onRejectInstallable: (model: string) => void;
};

export function DraftStudioReusePanel({
  reuseModels,
  reuseCatalog,
  reuseCatalogByModel,
  filteredReuseCatalog,
  reuseSearch,
  reuseCatalogStatus,
  reuseCatalogError,
  autoWiredReuse,
  inferredReuseSuggestions,
  installableReuseSuggestions,
  aiBusy,
  aiBusyLabel,
  onToggleReuse,
  onSearch,
  onReloadCatalog,
  onConfirmInferred,
  onRejectInferred,
  onConfirmInstallable,
  onRejectInstallable,
}: DraftStudioReusePanelProps) {
  return (
    <div className="mt-4" data-testid="stock-model-picker">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">
        Reuse existing Odoo models
      </p>
      <p className="mt-1 text-xs text-muted">
        Link stock Odoo models instead of inventing duplicates. Catalog is every
        non-custom model on this connection
        {reuseCatalog.length
          ? ` (${reuseCatalog.length.toLocaleString()} models)`
          : reuseCatalogStatus === "loading"
            ? " (loading…)"
            : ""}
        — not the full unused CE Apps list. After Job Autopilot or Install &amp;
        reuse, refresh so newly installed apps appear. Install &amp; reuse shows
        after the draft when a suggested app is not yet installed.
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {REUSE_SUGGESTIONS.map((m) => {
          const on = reuseModels.includes(m);
          const label = reuseCatalogByModel.get(m)?.name;
          return (
            <button
              key={m}
              type="button"
              onClick={() => onToggleReuse(m)}
              className={`chip font-mono ${on ? "is-selected" : ""}`}
              title={label || m}
            >
              {on ? "✓ " : ""}
              {label ? `${label} (${m})` : m}
            </button>
          );
        })}
      </div>
      <div className="mt-3 space-y-2">
        <Input
          type="search"
          placeholder="Search stock models by name or technical name…"
          value={reuseSearch}
          onChange={(e) => onSearch(e.target.value)}
          className="max-w-md font-mono text-xs"
          disabled={reuseCatalogStatus === "loading" && reuseCatalog.length === 0}
        />
        <div className="max-h-48 overflow-y-auto rounded-md border border-border-subtle bg-surface">
          {reuseCatalogStatus === "loading" && reuseCatalog.length === 0 ? (
            <p className="px-2 py-2 text-xs text-muted">Loading stock models…</p>
          ) : filteredReuseCatalog.length === 0 ? (
            <p className="px-2 py-2 text-xs text-muted">
              {reuseCatalogError || "No models match."}
            </p>
          ) : (
            filteredReuseCatalog.map((row) => {
              const on = reuseModels.includes(row.model);
              return (
                <button
                  key={row.model}
                  type="button"
                  onClick={() => onToggleReuse(row.model)}
                  className={`flex w-full items-start gap-2 border-b border-border-subtle px-2 py-1.5 text-left text-xs last:border-b-0 ${
                    on ? "bg-surface-raised" : "hover:bg-surface-raised/60"
                  }`}
                >
                  <span className="shrink-0 text-muted">{on ? "✓" : "+"}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-ink">{row.name}</span>
                    <span className="font-mono text-muted">
                      {row.model}
                      {row.link_only ? " · link-only" : ""}
                    </span>
                  </span>
                  <Badge variant="default" className="shrink-0 font-mono">
                    {row.app}
                  </Badge>
                </button>
              );
            })
          )}
        </div>
        {reuseCatalogError ? (
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs text-muted">{reuseCatalogError}</p>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              loading={reuseCatalogStatus === "loading"}
              onClick={onReloadCatalog}
            >
              Retry catalog
            </Button>
          </div>
        ) : null}
        {reuseSearch.trim() === "" && reuseCatalog.length > 120 ? (
          <p className="text-xs text-muted">
            Showing first 120 — type to search all{" "}
            {reuseCatalog.length.toLocaleString()} stock models on this
            instance.
          </p>
        ) : null}
      </div>
      {reuseModels.length > 0 ? (
        <p className="mt-2 font-mono text-xs text-muted">
          Selected: {reuseModels.join(", ")}
        </p>
      ) : null}
      {autoWiredReuse.length > 0 ? (
        <div
          className="mt-3 space-y-2 rounded-md border border-border-subtle bg-surface-muted p-3"
          data-testid="auto-wired-reuse"
        >
          <p className="text-xs font-medium text-ink">Auto-wired (link-only)</p>
          <p className="text-xs text-muted">
            Backend confirmed these stock models during apply-readiness because the
            apps are already installed. Install &amp; reuse is not offered in that
            case. Apply adds link-only M2O fields — it does not post orders,
            invoices, or stock moves.
          </p>
          <ul className="space-y-1 text-xs">
            {autoWiredReuse.map((d) => (
              <li key={String(d.model)} className="flex flex-wrap items-center gap-2">
                <Badge variant="default" className="font-mono">
                  {d.model}
                </Badge>
                <span className="text-muted">{d.reason ?? "Link-only reuse"}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {inferredReuseSuggestions.length > 0 ? (
        <div
          className="mt-3 space-y-2 rounded-md border border-border-subtle bg-surface-muted p-3"
          data-testid="inferred-reuse-suggestions"
        >
          <p className="text-xs font-medium text-ink">Suggested stock models</p>
          {aiBusy && aiBusyLabel ? (
            <p className="text-xs text-muted">{aiBusyLabel}</p>
          ) : null}
          {inferredReuseSuggestions.map((d) => (
            <div key={String(d.model)} className="rounded border border-border-subtle p-2">
              <p className="font-mono text-xs text-ink">{d.model}</p>
              <p className="mt-1 text-xs text-muted">
                Suggested — {d.reason}
                {d.link_only ? " (link-only)" : ""}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={aiBusy}
                  onClick={() => onConfirmInferred(String(d.model))}
                  data-testid={`confirm-reuse-${d.model}`}
                >
                  Use installed model
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={aiBusy}
                  onClick={() => onRejectInferred(String(d.model))}
                  data-testid={`reject-reuse-${d.model}`}
                >
                  Generate custom instead
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {installableReuseSuggestions.length > 0 ? (
        <div
          className="mt-3 space-y-2 rounded-md border border-border-subtle bg-surface-muted p-3"
          data-testid="installable-reuse-suggestions"
        >
          <p className="text-xs font-medium text-ink">Installable Odoo apps</p>
          <p className="text-xs text-muted">
            Install one app at a time — the others stay listed until you Install or
            generate custom. Installing does not clear sibling suggestions.
          </p>
          {installableReuseSuggestions.map((d) => (
            <div key={String(d.model)} className="rounded border border-border-subtle p-2">
              <p className="font-mono text-xs text-ink">{d.model}</p>
              <p className="mt-1 text-xs text-muted">
                Install <span className="font-mono">{d.module ?? "?"}</span> and reuse, or
                generate a custom model — {d.reason}
                {d.link_only ? " (link-only)" : ""}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={aiBusy}
                  onClick={() => onConfirmInstallable(String(d.model))}
                  data-testid={`confirm-install-reuse-${d.model}`}
                >
                  Install &amp; reuse
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={aiBusy}
                  onClick={() => onRejectInstallable(String(d.model))}
                  data-testid={`reject-install-reuse-${d.model}`}
                >
                  Generate custom instead
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
