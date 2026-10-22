"use client";

import Link from "next/link";
import { LockedExplainer } from "@/components/shell/LockedExplainer";
import { expertDestinationHref } from "@/lib/expert-journey";
import type { OverviewPageModel } from "./use-overview-page";

/**
 * Parts of the old CapabilitiesPostcard + CapabilityProbePanel not shown by the live
 * "What you can change here" list: check again, write mode, warnings, the first
 * locked feature explained, and the raw check details.
 */
export function CapabilityExtras({ vm }: { vm: OverviewPageModel }) {
  const conn = vm.connection;
  if (!conn) return null;
  const caps = conn.capabilities;
  const locked = caps?.unsupported ?? [];
  return (
    <div className="mt-4 space-y-3 border-t border-border-subtle pt-3" data-testid="capability-extras">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-ui-meta text-muted">
        <span>Write mode: <span className="text-ink">{conn.write_mode || "standard"}</span></span>
        {caps?.hosting_hint ? <span>Hosting: <span className="text-ink">{caps.hosting_hint}</span></span> : null}
        <span className="ml-auto flex gap-3">
          <Link href={expertDestinationHref(conn.id)} className="font-medium text-accent hover:underline">Ask Expert</Link>
          <button type="button" onClick={vm.onReprobe} disabled={vm.probing} data-testid="capability-reprobe"
            className="font-medium text-accent hover:underline disabled:opacity-50">
            {vm.probing ? "Checking…" : "Check again"}
          </button>
        </span>
      </div>
      {caps?.warnings?.length ? (
        <ul className="space-y-1 rounded-md bg-status-warning-subtle px-3 py-2 text-ui-meta text-status-warning-strong">
          {caps.warnings.map((w) => <li key={w.slice(0, 48)}>{w}</li>)}
        </ul>
      ) : null}
      {locked.length ? (
        <LockedExplainer
          title={`${locked[0].label} is locked`}
          why={locked[0].reason || "This feature is unavailable on this Odoo version or edition."}
          options={[
            "Move to an Odoo plan or version that includes it",
            "Try it first on a test copy running the same Odoo version",
            "Build it as a module and install it on a server you control",
            "Leave it out for now",
          ]}
          connectionId={conn.id}
        />
      ) : null}
      {caps ? (
        <details className="text-ui-meta text-muted">
          <summary className="cursor-pointer hover:text-ink">What we checked</summary>
          <div className="mt-2 space-y-1.5">
            {caps.message ? <p>{caps.message}</p> : null}
            {locked.length ? (
              <ul className="space-y-0.5">
                {locked.map((u) => <li key={u.id}><span className="text-ink">{u.label}</span>{u.reason ? `: ${u.reason}` : ""}</li>)}
              </ul>
            ) : null}
            {caps.installed_modules_sample?.length ? (
              <p>Modules sample: {caps.installed_modules_sample.slice(0, 12).join(", ")}{caps.installed_modules_sample.length > 12 ? "…" : ""}</p>
            ) : null}
          </div>
        </details>
      ) : null}
    </div>
  );
}
