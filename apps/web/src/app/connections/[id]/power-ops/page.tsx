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
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";
import { belowMinMajor, connectionMajor } from "@/lib/capabilities";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  BulkResultTable,
  type BulkRunResult,
} from "@/components/ui/BulkResultTable";
import { Callout } from "@/components/ui/Callout";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Input } from "@/components/ui/Input";
import { PageHeader, Skeleton } from "@/components/ui/layout-primitives";
import { Textarea } from "@/components/ui/Textarea";
import { PowerOpsErrorNotice } from "@/components/power-ops/PowerOpsErrorNotice";
import { PowerOpsResultCounts } from "@/components/power-ops/PowerOpsResultCounts";
import { PowerOpsStageRail } from "@/components/power-ops/PowerOpsStageRail";
import { PowerOpsStateGuide } from "@/components/power-ops/PowerOpsStateGuide";
import { OperateStudioBar } from "@/components/operate/OperateStudioBar";
import {
  CONFIRM_PHRASE,
  DRY_RUN_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  blockedRecipeGuide,
  emptyPowerOpsGuide,
  idlePowerOpsGuide,
  isDangerRecipe,
  partialFailureGuide,
  powerOpsHonestyGuide,
  powerOpsStepFromState,
  runUnlockReason,
  sanitizePowerOpsCopy,
  type PowerOpsErrorContext,
} from "@/lib/powerOpsScreen";
import "@/components/power-ops/power-ops-operate.css";

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
  const [recipeId, setRecipeId] = useState("mass_archive");
  const [model, setModel] = useState("account.move");
  const [domainText, setDomainText] = useState("[]");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorContext, setErrorContext] =
    useState<PowerOpsErrorContext>("load");
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<PowerOpsRunOut | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [dryRunKey, setDryRunKey] = useState<string | null>(null);
  const [listHydrated, setListHydrated] = useState(false);

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
      const locked = r.locked === true;
      const blocked = locked || blockedMajor || blockedModule;
      const blockReason = locked
        ? "Switched off"
        : blockedMajor
          ? `needs ≥${r.min_major}`
          : blockedModule
            ? probe?.reason || "module unavailable"
            : null;
      return {
        recipe: r,
        blocked,
        blockReason,
        locked,
        danger: isDangerRecipe(r),
      };
    });
  }, [recipes, connection, caps]);

  const selectedEntry = availableRecipes.find((e) => e.recipe.id === recipeId);
  const selected = selectedEntry?.recipe;
  const selectedBlocked = Boolean(selectedEntry?.blocked);
  const selectedBlockReason = selectedEntry?.blockReason;
  const selectedDanger = Boolean(selectedEntry?.danger);
  const canExecute = dryRunKey === runKey && !selectedBlocked;

  const lockedRecipes = availableRecipes.filter((e) => e.locked);
  const safeRecipes = availableRecipes.filter((e) => !e.locked && !e.danger);
  const dangerRecipes = availableRecipes.filter((e) => !e.locked && e.danger);

  const step = powerOpsStepFromState({
    recipeCount: recipes.length,
    hasRecipe: Boolean(selected),
    hasDryRun:
      dryRunKey === runKey || Boolean(result?.dry_run && dryRunKey === runKey),
    hasWriteResult: Boolean(result && !result.dry_run),
  });

  const unlockReason = runUnlockReason({ selectedBlocked, canExecute });
  const failureGuide = result
    ? partialFailureGuide({
        processed: result.processed,
        succeeded: result.succeeded,
        failed: result.failed,
        dryRun: result.dry_run,
      })
    : null;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setListHydrated(false);
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
            !row.locked &&
            !(
              conn.capabilities?.major != null &&
              (row.min_major ?? 16) > conn.capabilities.major
            ),
        );
        if (firstOk) setRecipeId(firstOk.id);
      } catch (err) {
        if (!cancelled) {
          setErrorContext("load");
          setError(
            err instanceof Error ? err.message : "Failed to load Power Ops",
          );
        }
      } finally {
        if (!cancelled) setListHydrated(true);
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

  async function reprobeAndReload() {
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
      const [r, c] = await Promise.all([
        api.powerOpsRecipes(connectionId),
        api.powerOpsCapabilities(connectionId),
      ]);
      setRecipes(r.recipes);
      setCaps(c);
    } catch (err) {
      setErrorContext("probe");
      setError(err instanceof Error ? err.message : "Probe failed");
    } finally {
      setProbing(false);
    }
  }

  async function run(dryRun: boolean, phrase?: string) {
    if (selectedBlocked) {
      setErrorContext("blocked");
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
        setErrorContext("domain");
        throw new Error("Invalid domain JSON - use Odoo domain list, e.g. []");
      }
      const res = await api.powerOpsRun(connectionId, {
        recipe_id: recipeId,
        model,
        domain,
        dry_run: dryRun,
        ...(dryRun
          ? {}
          : {
              confirm_advanced: true,
              confirm_phrase: phrase || CONFIRM_PHRASE,
            }),
      });
      setResult(res);
      setNotice(sanitizePowerOpsCopy(res.message));
      if (dryRun) setDryRunKey(runKey);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmOpen(true);
        setErrorContext("run");
        setError(err.warning);
      } else {
        setErrorContext(dryRun ? "dry_run" : "run");
        setError(err instanceof Error ? err.message : "Run failed");
      }
    } finally {
      setBusy(false);
    }
  }

  function RecipeCard({ entry }: { entry: (typeof availableRecipes)[number] }) {
    const { recipe: r, blocked, blockReason, danger } = entry;
    const active = recipeId === r.id;
    return (
      <button
        type="button"
        disabled={blocked}
        onClick={() => setRecipeId(r.id)}
        className="po-recipe"
        data-active={active ? "true" : "false"}
        data-danger={danger ? "true" : "false"}
        data-testid={`power-ops-recipe-${r.id}`}
      >
        <div className="po-recipe-head">
          <p className="po-recipe-name">{sanitizePowerOpsCopy(r.name)}</p>
          <div className="po-badge-row">
            {danger ? <Badge variant="danger">Danger zone</Badge> : null}
            {r.min_major != null ? (
              <Badge variant="info">Odoo ≥{r.min_major}</Badge>
            ) : null}
            {blocked && blockReason ? (
              <Badge variant="warning">{blockReason}</Badge>
            ) : null}
          </div>
        </div>
        <p className="po-recipe-desc">{sanitizePowerOpsCopy(r.description)}</p>
        {r.tags?.length || r.requires_modules?.length ? (
          <p className="po-badge-row mt-2">
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
    <div className="power-ops-operate" data-testid="power-ops-page">
      <PageHeader title={PAGE_TITLE} description={PAGE_DESCRIPTION} />
      <PowerOpsStageRail step={step} />

      <VersionAwarenessBanner capabilities={connection?.capabilities} />
      {connection ? <FirstWriteInterstitial connection={connection} /> : null}
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
              setErrorContext("probe");
              setError(err instanceof Error ? err.message : "Probe failed");
            } finally {
              setProbing(false);
            }
          })();
        }}
      />

      <OperateStudioBar
        className="mt-3"
        testId="power-ops-honesty"
        tone="warning"
        title={powerOpsHonestyGuide().title}
        why={powerOpsHonestyGuide().why}
        next={powerOpsHonestyGuide().next}
      />

      <div className="po-desk" data-testid="power-ops-desk">
        {caps?.philosophy ? (
          <Callout
            variant="info"
            title="How this works"
            className="mt-4"
            testId="power-ops-philosophy"
          >
            {sanitizePowerOpsCopy(caps.philosophy)}
          </Callout>
        ) : null}

        {error ? (
          <PowerOpsErrorNotice
            className="mt-4"
            message={error}
            context={errorContext}
            onDismiss={() => setError(null)}
            onRetry={
              errorContext === "load" || errorContext === "probe"
                ? () => void reprobeAndReload()
                : errorContext === "dry_run"
                  ? () => void run(true)
                  : undefined
            }
          />
        ) : null}
        {notice ? (
          <Callout
            variant="info"
            title="Notice"
            className="mt-4"
            testId="power-ops-notice"
          >
            {notice}
          </Callout>
        ) : null}

        {busy ? (
          <div
            className="po-progress"
            aria-busy="true"
            data-testid="power-ops-progress"
            role="status"
          >
            {confirmOpen ? "Running recipe…" : "Test-running recipe…"}
          </div>
        ) : null}

        <section
          className="po-panel"
          data-testid="power-ops-recipes"
          aria-labelledby="power-ops-recipes-title"
        >
          <h2 id="power-ops-recipes-title" className="po-panel-title">
            Recipes
          </h2>
          <p className="po-panel-sub">
            Safe recipes first. Danger-zone recipes need test run counts, then
            the risk phrase.
          </p>
          {!listHydrated ? (
            <div
              className="po-recipe-grid"
              data-testid="power-ops-recipes-loading"
            >
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
            </div>
          ) : recipes.length === 0 ? (
            <PowerOpsStateGuide
              tone="accent"
              testId="power-ops-empty-guide"
              guide={emptyPowerOpsGuide()}
              actions={
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={probing}
                  onClick={() => void reprobeAndReload()}
                >
                  Re-probe connection
                </Button>
              }
            />
          ) : (
            <>
              {listHydrated && !result && dryRunKey !== runKey ? (
                <PowerOpsStateGuide
                  className="!mt-0 mb-3"
                  tone="accent"
                  testId="power-ops-idle-guide"
                  guide={idlePowerOpsGuide()}
                />
              ) : null}
              {safeRecipes.length > 0 ? (
                <div className="po-recipe-grid">
                  {safeRecipes.map((entry) => (
                    <RecipeCard key={entry.recipe.id} entry={entry} />
                  ))}
                </div>
              ) : null}
              {dangerRecipes.length > 0 ? (
                <div
                  className="po-danger-band"
                  data-testid="power-ops-danger-zone"
                >
                  <p className="po-danger-band-title">Danger zone</p>
                  <p className="po-danger-band-body">
                    Destructive recipes. Test run first. Run recipe asks for the
                    risk phrase.
                  </p>
                  <div className="po-recipe-grid">
                    {dangerRecipes.map((entry) => (
                      <RecipeCard key={entry.recipe.id} entry={entry} />
                    ))}
                  </div>
                </div>
              ) : null}
              {lockedRecipes.length > 0 ? (
                <div className="po-locked-band" data-testid="power-ops-locked">
                  <p className="po-danger-band-title">
                    Switched off to keep your books safe
                  </p>
                  <p className="po-danger-band-body">
                    {lockedRecipes[0].recipe.locked_reason ??
                      "Ingenium does not change accounting entries or delete records in bulk."}
                  </p>
                  <ul className="po-locked-list">
                    {lockedRecipes.map((e) => (
                      <li
                        key={e.recipe.id}
                        data-testid={`power-ops-locked-${e.recipe.id}`}
                      >
                        <Badge variant="lock">Locked</Badge>{" "}
                        {sanitizePowerOpsCopy(e.recipe.name)}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          )}
        </section>

        {selectedBlocked && selectedBlockReason ? (
          <PowerOpsStateGuide
            tone="warning"
            live
            testId="power-ops-blocked-guide"
            guide={blockedRecipeGuide({
              blockReason: selectedBlockReason,
              minMajor: selected?.min_major,
              major,
            })}
          />
        ) : null}

        {selected ? (
          <section
            className="po-panel"
            aria-labelledby="power-ops-run-title"
            data-testid="power-ops-run-panel"
          >
            <h2 id="power-ops-run-title" className="po-panel-title">
              Run · {sanitizePowerOpsCopy(selected.name)}
            </h2>
            <p className="po-panel-sub">
              {selectedDanger
                ? "Destructive recipe. Confirm only after test run counts look right."
                : "Configure model and domain, test run, then run."}
            </p>
            <ul className="po-steps">
              {selected.steps.map((s) => (
                <li key={s.label}>
                  {sanitizePowerOpsCopy(s.label)} ({s.kind}
                  {s.method ? `:${s.method}` : ""})
                </li>
              ))}
            </ul>
            {selected.risks?.length ? (
              <Callout
                variant="warning"
                title="Recipe risks"
                className="mb-3"
                testId="power-ops-risks"
              >
                <ul className="list-disc space-y-1 pl-4 text-sm">
                  {selected.risks.map((risk) => (
                    <li key={risk}>{sanitizePowerOpsCopy(risk)}</li>
                  ))}
                </ul>
              </Callout>
            ) : null}
            <Input
              label="Model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="font-mono text-sm"
            />
            <div className="mt-3">
              <Textarea
                label="Domain (JSON list)"
                rows={3}
                value={domainText}
                onChange={(e) => setDomainText(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
            <div className="po-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={busy || selectedBlocked}
                loading={busy && !confirmOpen}
                onClick={() => void run(true)}
                data-testid="power-ops-dry-run-btn"
              >
                {DRY_RUN_CTA}
              </Button>
              <Button
                type="button"
                variant="primary"
                disabled={busy || !canExecute}
                title={unlockReason ?? undefined}
                onClick={() => setConfirmOpen(true)}
                data-testid="power-ops-run-btn"
              >
                {PRIMARY_CTA}
              </Button>
              {unlockReason ? (
                <p className="po-primary-reason">{unlockReason}</p>
              ) : null}
            </div>
          </section>
        ) : null}

        {result ? (
          <section
            className="po-panel"
            data-testid="power-ops-result-block"
            aria-labelledby="power-ops-result-title"
          >
            <h2 id="power-ops-result-title" className="po-panel-title">
              {result.dry_run ? "Test run result" : "Run result"}
            </h2>
            <p className="po-result-label" data-testid="power-ops-result-label">
              {result.dry_run
                ? "Test run result (no writes)"
                : "Run result (writes applied)"}
            </p>
            <PowerOpsResultCounts
              processed={result.processed}
              succeeded={result.succeeded}
              failed={result.failed}
              dryRun={result.dry_run}
            />
            {failureGuide ? (
              <PowerOpsStateGuide
                tone="warning"
                live
                testId="power-ops-partial-guide"
                guide={failureGuide}
              />
            ) : null}
            {result.logs.length > 0 ? (
              <div className="mt-4">
                <BulkResultTable
                  result={toBulkResult(result, recipeId, model)}
                />
              </div>
            ) : result.message ? (
              <p className="mt-3 text-sm text-muted">
                {sanitizePowerOpsCopy(result.message)}
              </p>
            ) : null}
          </section>
        ) : null}

        <ConfirmDialogV2
          open={confirmOpen}
          riskLevel="danger"
          title={`Run ${selected?.name ?? "Power Ops recipe"}`}
          warning={
            selected
              ? `This will run "${sanitizePowerOpsCopy(selected.name)}" against live records. Test run first when unsure.`
              : "Destructive bulk RPC on live data."
          }
          risks={
            selected?.risks?.length
              ? selected.risks.map(sanitizePowerOpsCopy)
              : [
                  "Bulk writes or deletes on live ERP data",
                  "Rollback may be incomplete for some operations",
                ]
          }
          blastRadius={[
            `Recipe: ${selected?.id ?? recipeId}`,
            `Model: ${model}`,
            `Domain: ${domainText}`,
          ]}
          phrase={CONFIRM_PHRASE}
          busy={busy}
          onCancel={() => setConfirmOpen(false)}
          onConfirm={(typed) => void run(false, typed)}
        />
      </div>
    </div>
  );
}
