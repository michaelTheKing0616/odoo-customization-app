"use client";

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
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { belowMinMajor, connectionMajor } from "@/lib/capabilities";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { BulkResultTable, type BulkRunResult } from "@/components/ui/BulkResultTable";
import { Callout } from "@/components/ui/Callout";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { Textarea } from "@/components/ui/Textarea";

const CONFIRM_PHRASE = "I understand the risks";

function isDangerRecipe(recipe: PowerOpsRecipe): boolean {
  const tags = (recipe.tags ?? []).map((t) => t.toLowerCase());
  if (tags.some((t) => t.includes("danger") || t.includes("destructive"))) return true;
  const id = recipe.id.toLowerCase();
  return id.includes("purge") || id.includes("delete") || id.includes("unlink");
}

function toBulkResult(
  result: PowerOpsRunOut,
  recipeId: string,
  model: string,
): BulkRunResult {
  return {
    run_id: "power-ops",
    operation: recipeId,
    model,
    total: result.processed,
    succeeded: result.succeeded,
    failed: result.failed,
    per_record: result.logs.map((l) => ({
      record_id: l.record_id,
      display_name: l.step,
      ok: l.ok,
      error: l.error,
    })),
    dry_run: result.dry_run,
    message: result.message,
  };
}

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
  const [dryRunKey, setDryRunKey] = useState<string | null>(null);

  const major = connectionMajor(connection);
  const runKey = `${recipeId}|${model}|${domainText}`;

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
      return { recipe: r, blocked, blockReason, danger: isDangerRecipe(r) };
    });
  }, [recipes, connection, caps]);

  const selectedEntry = availableRecipes.find((e) => e.recipe.id === recipeId);
  const selected = selectedEntry?.recipe;
  const selectedBlocked = Boolean(selectedEntry?.blocked);
  const selectedBlockReason = selectedEntry?.blockReason;
  const canExecute = dryRunKey === runKey && !selectedBlocked;

  const safeRecipes = availableRecipes.filter((e) => !e.danger);
  const dangerRecipes = availableRecipes.filter((e) => e.danger);

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
        const firstOk = r.recipes.find(
          (row) =>
            !(
              conn.capabilities?.major != null &&
              (row.min_major ?? 16) > conn.capabilities.major
            ),
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
    setDryRunKey(null);
  }, [selected, recipeId]);

  useEffect(() => {
    setDryRunKey(null);
  }, [model, domainText]);

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
      if (dryRun) setDryRunKey(runKey);
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

  function RecipeCard({
    entry,
  }: {
    entry: (typeof availableRecipes)[number];
  }) {
    const { recipe: r, blocked, blockReason, danger } = entry;
    const active = recipeId === r.id;
    return (
      <button
        type="button"
        disabled={blocked}
        onClick={() => setRecipeId(r.id)}
        className={`w-full rounded-md border p-4 text-left transition ${
          active
            ? "border-accent bg-accent-subtle/30 ring-2 ring-accent"
            : "border-border-subtle bg-surface hover:border-accent/50"
        } ${blocked ? "cursor-not-allowed opacity-50" : ""}`}
        data-testid={`power-ops-recipe-${r.id}`}
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <p className="font-semibold text-ink">{r.name}</p>
          <div className="flex flex-wrap gap-1">
            {danger ? <Badge variant="danger">Danger zone</Badge> : null}
            {r.min_major != null ? (
              <Badge variant="info">Odoo ≥{r.min_major}</Badge>
            ) : null}
            {blocked && blockReason ? (
              <Badge variant="warning">{blockReason}</Badge>
            ) : null}
          </div>
        </div>
        <p className="mt-2 text-sm text-muted">{r.description}</p>
        {(r.tags?.length || r.requires_modules?.length) ? (
          <p className="mt-2 flex flex-wrap gap-1">
            {r.tags?.map((t) => (
              <Badge key={t} variant="default">
                {t}
              </Badge>
            ))}
            {r.requires_modules?.map((m) => (
              <Badge key={m} variant="lock">
                {m}
              </Badge>
            ))}
          </p>
        ) : null}
      </button>
    );
  }

  return (
    <div className="mx-auto max-w-5xl" data-testid="power-ops-page">
      <PageHeader
        title="Power Ops"
        description="Multi-step bulk RPC recipes — the same class of power as Odoo.sh scripts, usable on Odoo Online when the API allows."
      />
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
              const probeResult = await api.probeConnection(connectionId);
              setConnection((prev) =>
                prev
                  ? {
                      ...prev,
                      server_version: probeResult.server_version,
                      capabilities: probeResult.capabilities,
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
      {caps?.philosophy ? (
        <Callout variant="info" title="Philosophy" className="mt-4">
          {caps.philosophy}
        </Callout>
      ) : null}

      {error ? <ErrorNotice message={error} className="mt-4" /> : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

      <section className="mt-8 space-y-4">
        <h2 className="text-lg font-semibold text-ink">Recipes</h2>
        {safeRecipes.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {safeRecipes.map((entry) => (
              <RecipeCard key={entry.recipe.id} entry={entry} />
            ))}
          </div>
        ) : null}
        {dangerRecipes.length > 0 ? (
          <>
            <Callout variant="danger" title="Danger zone">
              Destructive recipes — dry-run first, then confirm with phrase.
            </Callout>
            <div className="grid gap-3 sm:grid-cols-2">
              {dangerRecipes.map((entry) => (
                <RecipeCard key={entry.recipe.id} entry={entry} />
              ))}
            </div>
          </>
        ) : null}
      </section>

      {selectedBlocked && selectedBlockReason ? (
        <Callout variant="warning" title="Recipe blocked" className="mt-4">
          {selectedBlockReason.startsWith("needs")
            ? `This recipe requires Odoo major ≥${selected?.min_major}. Connected major: ${major ?? "unknown (re-probe)"}.`
            : selectedBlockReason}
        </Callout>
      ) : null}

      {selected ? (
        <Card className="mt-6 space-y-4 p-6">
          <h2 className="text-lg font-semibold text-ink">Run · {selected.name}</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            {selected.steps.map((s) => (
              <li key={s.label}>
                {s.label} ({s.kind}
                {s.method ? `:${s.method}` : ""})
              </li>
            ))}
          </ul>
          <Input
            label="Model"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="font-mono text-sm"
          />
          <Textarea
            label="Domain (JSON list)"
            rows={3}
            value={domainText}
            onChange={(e) => setDomainText(e.target.value)}
            className="font-mono text-xs"
          />
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={busy || selectedBlocked}
              loading={busy}
              onClick={() => void run(true)}
            >
              Dry-run
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={busy || !canExecute}
              title={
                !canExecute && !selectedBlocked
                  ? "Run dry-run first for this recipe, model, and domain"
                  : undefined
              }
              onClick={() => setConfirmOpen(true)}
            >
              Execute
            </Button>
          </div>
          {!canExecute && !selectedBlocked ? (
            <p className="text-xs text-muted">
              Execute unlocks after a successful dry-run with the same recipe, model, and domain.
            </p>
          ) : null}
        </Card>
      ) : null}

      {result && result.logs.length > 0 ? (
        <Card className="mt-6 p-6">
          <BulkResultTable result={toBulkResult(result, recipeId, model)} />
        </Card>
      ) : result ? (
        <Card className="mt-6 p-4">
          <p className="text-sm text-muted">{result.message}</p>
        </Card>
      ) : null}

      <ConfirmDialogV2
        open={confirmOpen}
        riskLevel="danger"
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
  );
}
