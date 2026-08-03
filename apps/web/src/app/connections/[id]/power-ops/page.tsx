"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  ConfirmationRequiredError,
  Connection,
  PowerOpsCapabilities,
  PowerOpsRecipe,
  PowerOpsRunOut,
} from "@/lib/api";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { belowMinMajor, connectionMajor } from "@/lib/capabilities";

const CONFIRM_PHRASE = "I understand the risks";

export default function PowerOpsPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [probing, setProbing] = useState(false);
  const [recipes, setRecipes] = useState<PowerOpsRecipe[]>([]);
  const [caps, setCaps] = useState<PowerOpsCapabilities | null>(null);
  const [recipeId, setRecipeId] = useState("purge_journal_entries");
  const [model, setModel] = useState("account.move");
  const [domainText, setDomainText] = useState("[]");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<PowerOpsRunOut | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const major = connectionMajor(connection);

  const availableRecipes = useMemo(() => {
    const byId = new Map(
      (caps?.power_ops_recipes || []).map((r) => [r.id, r] as const),
    );
    return recipes.map((r) => {
      const blockedMajor = belowMinMajor(connection, r.min_major ?? 16);
      const probe = byId.get(r.id);
      const blockedModule = probe ? probe.available === false : false;
      const blocked = blockedMajor || blockedModule;
      const blockReason = blockedMajor
        ? `needs ≥${r.min_major}`
        : blockedModule
          ? probe?.reason || "module unavailable"
          : null;
      return { recipe: r, blocked, blockReason };
    });
  }, [recipes, connection, caps]);

  const selectedEntry = availableRecipes.find((e) => e.recipe.id === recipeId);
  const selected = selectedEntry?.recipe;
  const selectedBlocked = Boolean(selectedEntry?.blocked);
  const selectedBlockReason = selectedEntry?.blockReason;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [r, c, conn] = await Promise.all([
          api.powerOpsRecipes(connectionId),
          api.powerOpsCapabilities(connectionId),
          api.getConnection(connectionId),
        ]);
        if (cancelled) return;
        setRecipes(r.recipes);
        setCaps(c);
        setConnection(conn);
        // Prefer first recipe that meets min_major
        const firstOk = r.recipes.find(
          (row) => !(conn.capabilities?.major != null && (row.min_major ?? 16) > conn.capabilities.major),
        );
        if (firstOk) setRecipeId(firstOk.id);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load Power Ops");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [connectionId]);

  useEffect(() => {
    if (selected && selected.model !== "*") {
      setModel(selected.model);
    }
  }, [selected]);

  async function run(dryRun: boolean, phrase?: string) {
    if (selectedBlocked) {
      setError(
        `Recipe requires Odoo ≥${selected?.min_major ?? "?"}; connected major is ${major ?? "unknown"}`,
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let domain: unknown[] = [];
      try {
        domain = JSON.parse(domainText) as unknown[];
        if (!Array.isArray(domain)) throw new Error("domain must be a list");
      } catch {
        throw new Error("Invalid domain JSON — use Odoo domain list, e.g. []");
      }
      const res = await api.powerOpsRun(connectionId, {
        recipe_id: recipeId,
        model,
        domain,
        dry_run: dryRun,
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Run failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="odoo-shell min-h-screen px-6 py-10">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap gap-3 text-sm">
          <Link href={`/connections/${connectionId}`} className="text-[var(--odoo-primary-light)] hover:underline">
            ← Metadata
          </Link>
          <Link href={`/connections/${connectionId}/import`} className="text-[var(--odoo-primary-light)] hover:underline">
            Bulk import
          </Link>
          <Link href={`/connections/${connectionId}/bulk-suite`} className="text-[var(--odoo-primary-light)] hover:underline">
            Bulk Suite
          </Link>
          <Link href={`/connections/${connectionId}/cron-manager`} className="text-[var(--odoo-primary-light)] hover:underline">
            Cron Manager
          </Link>
          <Link href={`/connections/${connectionId}/housekeeping`} className="text-[var(--odoo-primary-light)] hover:underline">
            Housekeeping
          </Link>
          <Link href={`/connections/${connectionId}/cron-manager`} className="text-[var(--odoo-primary-light)] hover:underline">
            Cron Manager
          </Link>
          <Link href={`/connections/${connectionId}/housekeeping`} className="text-[var(--odoo-primary-light)] hover:underline">
            Housekeeping
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[var(--odoo-sheet-fg)]">
          Power Ops
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--odoo-muted)]">
          Multi-step bulk RPC recipes — the same class of power as Odoo.sh scripts, usable on
          Odoo Online when the API allows. Example: reset journal entries to draft, then delete.
        </p>
        <VersionAwarenessBanner capabilities={connection?.capabilities} />
        <CapabilityProbePanel
          capabilities={connection?.capabilities}
          defaultOpen={false}
          className="mt-2"
          refreshing={probing}
          onRefresh={() => {
            void (async () => {
              setProbing(true);
              setError(null);
              try {
                const result = await api.probeConnection(connectionId);
                setConnection((prev) =>
                  prev
                    ? {
                        ...prev,
                        server_version: result.server_version,
                        capabilities: result.capabilities,
                      }
                    : prev,
                );
              } catch (err) {
                setError(err instanceof Error ? err.message : "Probe failed");
              } finally {
                setProbing(false);
              }
            })();
          }}
        />
        {caps?.philosophy && (
          <p className="mt-2 text-sm text-[var(--odoo-success)]">{caps.philosophy}</p>
        )}

        <section className="odoo-sheet mt-6 space-y-4 p-4">
          <label className="block text-sm">
            Recipe
            <select
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
              value={recipeId}
              onChange={(e) => setRecipeId(e.target.value)}
            >
              {availableRecipes.map(({ recipe: r, blocked, blockReason }) => (
                <option key={r.id} value={r.id} disabled={blocked}>
                  {blocked ? "⚠ " : ""}
                  {r.name}
                  {r.tags?.length ? ` [${r.tags.join(", ")}]` : ""}
                  {blocked && blockReason ? ` (${blockReason})` : ""}
                </option>
              ))}
            </select>
          </label>
          {selectedBlocked && (
            <p className="text-sm text-[var(--odoo-danger)]">
              {selectedBlockReason?.startsWith("needs")
                ? `This recipe requires Odoo major ≥${selected?.min_major}. Connected major: ${major ?? "unknown (re-probe)"}.`
                : selectedBlockReason || "Recipe unavailable on this database."}
            </p>
          )}
          {selected && (
            <div className="text-sm text-[var(--odoo-muted)]">
              <p>{selected.description}</p>
              {(selected.tags?.length || selected.requires_modules?.length) && (
                <p className="mt-1 text-xs">
                  {selected.tags?.length ? (
                    <span>Tags: {selected.tags.join(", ")}. </span>
                  ) : null}
                  {selected.requires_modules?.length ? (
                    <span>Requires modules: {selected.requires_modules.join(", ")}.</span>
                  ) : null}
                  {selected.min_major != null ? (
                    <span> Min Odoo major: {selected.min_major}.</span>
                  ) : null}
                </p>
              )}
              <ul className="mt-2 list-disc pl-5">
                {selected.steps.map((s) => (
                  <li key={s.label}>
                    {s.label} ({s.kind}
                    {s.method ? `:${s.method}` : ""})
                  </li>
                ))}
              </ul>
            </div>
          )}
          <label className="block text-sm">
            Model
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Domain (JSON list)
            <textarea
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-xs"
              rows={3}
              value={domainText}
              onChange={(e) => setDomainText(e.target.value)}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy || selectedBlocked}
              onClick={() => void run(true)}
              className="border border-[var(--odoo-primary)] px-3 py-1.5 text-sm text-[var(--odoo-primary)] disabled:opacity-50"
            >
              Dry-run
            </button>
            <button
              type="button"
              disabled={busy || selectedBlocked}
              onClick={() => setConfirmOpen(true)}
              className="bg-[var(--odoo-danger)] px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              Execute
            </button>
          </div>
          {notice && <p className="text-sm text-[var(--odoo-success)]">{notice}</p>}
          {error && <p className="text-sm text-[var(--odoo-danger)]">{error}</p>}
          {result && (
            <pre className="max-h-64 overflow-auto bg-[#f8f9fa] p-2 text-xs text-[#1f1f1f]">
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </section>

        <ConfirmDialog
          open={confirmOpen}
          title="Execute Power Ops recipe"
          warning={
            selected
              ? `This will run “${selected.name}” against live records. Dry-run first when unsure.`
              : "Destructive bulk RPC on live data."
          }
          risks={[
            "Bulk writes or deletes on live ERP data",
            "Rollback may be incomplete for some operations",
          ]}
          phrase={CONFIRM_PHRASE}
          busy={busy}
          onCancel={() => setConfirmOpen(false)}
          onConfirm={(typed) => void run(false, typed)}
        />
      </div>
    </main>
  );
}
