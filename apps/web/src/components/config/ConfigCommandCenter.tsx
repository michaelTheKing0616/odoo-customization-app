"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  AppsPackItem,
  ConfirmationRequiredError,
  MasterPackItem,
  NumberingCatalogItem,
  RecipeCard,
  RecipePlanOut,
  SettingsBoardOut,
} from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Input } from "@/components/ui/Input";
import { ConfigErrorNotice } from "@/components/config/ConfigErrorNotice";
import { ConfigStageRail } from "@/components/config/ConfigStageRail";
import { ConfigStateGuide } from "@/components/config/ConfigStateGuide";
import {
  APPLY_CTA,
  CONFIRM_PHRASE,
  DRY_RUN_CTA,
  PRIMARY_CTA,
  applyKeyForPanel,
  applyUnlockReason,
  appliedConfigGuide,
  configHonestyGuide,
  configStepFromState,
  emptyConfigGuide,
  idleConfigGuide,
  planHonestyLabel,
  primaryCtaForPanel,
  sanitizeConfigCopy,
  type ConfigErrorContext,
  type ConfigPanelId,
} from "@/lib/configScreen";
import { Term } from "@/components/ui/Term";

type PendingApply = {
  label: string;
  run: (confirmed: boolean) => Promise<RecipePlanOut>;
};

function PlanPreview({ plan }: { plan: RecipePlanOut | null }) {
  if (!plan) return null;
  const dry = Boolean(plan.dry_run);
  return (
    <div className="mt-4" data-testid="recipe-plan-preview" data-dry-run={dry ? "true" : "false"}>
      <p className="cfg-result-label" data-testid="config-result-label">
        {planHonestyLabel(dry)}
      </p>
      <p className="cfg-lead" style={{ marginTop: 8 }}>
        {sanitizeConfigCopy(
          plan.message || (dry ? "Review steps, then Apply." : "Done."),
        )}
      </p>
      {plan.warnings?.length ? (
        <ul className="mt-2 list-disc pl-4 text-xs text-muted">
          {plan.warnings.map((w) => (
            <li key={w}>{sanitizeConfigCopy(w)}</li>
          ))}
        </ul>
      ) : null}
      <ul className="cfg-plan-steps">
        {plan.steps.map((s, i) => (
          <li key={`${s.op}-${s.target}-${i}`}>
            <span className="font-mono text-ink">{s.op}</span>
            {" · "}
            {s.target}
            {" - "}
            {sanitizeConfigCopy(s.detail)}
          </li>
        ))}
      </ul>
      {plan.applied?.length ? (
        <p className="mt-2 text-xs text-ink">{plan.applied.join(" · ")}</p>
      ) : null}
    </div>
  );
}

function JobCard({
  card,
  onOpen,
  openLabel = "Open",
}: {
  card: RecipeCard;
  onOpen: () => void;
  openLabel?: string;
}) {
  const phaseVariant =
    card.phase === "p0" ? "success" : card.phase === "p1" ? "info" : "default";
  return (
    <div className="cfg-recipe" data-testid={`recipe-card-${card.id}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="cfg-recipe-name">{sanitizeConfigCopy(card.title)}</p>
          <p className="cfg-recipe-desc">{sanitizeConfigCopy(card.blurb)}</p>
        </div>
        <Badge variant={phaseVariant as "success" | "info" | "default"}>
          {card.phase.toUpperCase()}
        </Badge>
      </div>
      <div className="cfg-recipe-foot">
        <span className="text-xs text-muted">{sanitizeConfigCopy(card.clicks)}</span>
        <Button type="button" size="sm" variant="secondary" onClick={onOpen}>
          {openLabel}
        </Button>
      </div>
    </div>
  );
}

export function ConfigCommandCenter({ connectionId }: { connectionId: string }) {
  const [cards, setCards] = useState<RecipeCard[]>([]);
  const [panel, setPanel] = useState<ConfigPanelId>("home");
  const [error, setError] = useState<string | null>(null);
  const [errorContext, setErrorContext] = useState<ConfigErrorContext>("load");
  const [busy, setBusy] = useState(false);
  const [listHydrated, setListHydrated] = useState(false);
  const [plan, setPlan] = useState<RecipePlanOut | null>(null);
  const [pending, setPending] = useState<PendingApply | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [dryRunKey, setDryRunKey] = useState<string | null>(null);

  const [day1, setDay1] = useState({
    name: "",
    currency_code: "USD",
    country_code: "",
    language_code: "en_US",
    email: "",
    phone: "",
  });
  const [numberingCatalog, setNumberingCatalog] = useState<NumberingCatalogItem[]>([]);
  const [numberingKeys, setNumberingKeys] = useState<string[]>([]);
  const [appsPacks, setAppsPacks] = useState<AppsPackItem[]>([]);
  const [selectedPack, setSelectedPack] = useState("");
  const [settings, setSettings] = useState<SettingsBoardOut | null>(null);
  const [settingsQuery, setSettingsQuery] = useState("");
  const [settingsDraft, setSettingsDraft] = useState<Record<string, string>>({});
  const [mc, setMc] = useState({ name: "", currency_code: "USD", country_code: "" });
  const [masterPacks, setMasterPacks] = useState<MasterPackItem[]>([]);
  const [masterId, setMasterId] = useState("uom_basic");

  const fingerprint = useMemo(() => {
    switch (panel) {
      case "day1":
        return [
          day1.name,
          day1.currency_code,
          day1.country_code,
          day1.language_code,
          day1.email,
          day1.phone,
        ].join("|");
      case "numbering":
        return [...numberingKeys].sort().join(",");
      case "apps-pack":
        return selectedPack;
      case "settings-board":
        return Object.entries(settingsDraft)
          .map(([k, v]) => `${k}=${v}`)
          .sort()
          .join("&");
      case "multi-company":
        return [mc.name, mc.currency_code, mc.country_code].join("|");
      case "master-packs":
        return masterId;
      default:
        return "";
    }
  }, [panel, day1, numberingKeys, selectedPack, settingsDraft, mc, masterId]);

  const applyKey = applyKeyForPanel(panel, fingerprint);
  const canApply = dryRunKey === applyKey && Boolean(plan?.dry_run);
  const hasWriteResult = Boolean(plan && !plan.dry_run);
  const step = configStepFromState({
    panel,
    recipeCount: cards.length,
    hasDryRun: canApply || (Boolean(plan?.dry_run) && dryRunKey === applyKey),
    hasWriteResult,
  });
  const unlockReason = applyUnlockReason({ canApply, panel });
  const primaryLabel = primaryCtaForPanel(panel);

  const loadHome = useCallback(async () => {
    setListHydrated(false);
    setErrorContext("load");
    try {
      setCards(await api.listConfigRecipes(connectionId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setListHydrated(true);
    }
  }, [connectionId]);

  useEffect(() => {
    void loadHome();
  }, [loadHome]);

  const openPanel = useCallback(
    async (id: ConfigPanelId) => {
      setPanel(id);
      setPlan(null);
      setDryRunKey(null);
      setError(null);
      setErrorContext("panel");
      try {
        if (id === "numbering") {
          const cat = await api.numberingCatalog(connectionId);
          setNumberingCatalog(cat);
          setNumberingKeys(cat.map((c) => c.key));
        } else if (id === "apps-pack") {
          const packs = await api.listAppsPacks(connectionId);
          setAppsPacks(packs);
          setSelectedPack(packs[0]?.id ?? "");
        } else if (id === "settings-board") {
          const board = await api.getSettingsBoard(connectionId);
          setSettings(board);
          const draft: Record<string, string> = {};
          for (const [k, v] of Object.entries(board.values || {})) {
            draft[k] = v == null ? "" : String(v);
          }
          setSettingsDraft(draft);
        } else if (id === "master-packs") {
          const packs = await api.listMasterPacks(connectionId);
          setMasterPacks(packs);
          setMasterId(packs[0]?.id ?? "uom_basic");
        } else if (id === "day1") {
          const cos = await api.listCompanies(connectionId);
          if (cos[0]?.name) {
            setDay1((d) => ({ ...d, name: cos[0].name || d.name }));
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [connectionId],
  );

  const runPlan = useCallback(
    async (
      label: string,
      dryRun: boolean,
      run: (confirmed: boolean) => Promise<RecipePlanOut>,
      context: ConfigErrorContext = dryRun ? "dry_run" : "apply",
    ) => {
      setBusy(true);
      setError(null);
      setErrorContext(context);
      try {
        if (dryRun) {
          const next = await run(false);
          setPlan(next);
          setDryRunKey(applyKey);
          return;
        }
        setPlan(await run(false));
        setDryRunKey(applyKey);
      } catch (err) {
        if (err instanceof ConfirmationRequiredError) {
          setPending({ label, run });
          setConfirmOpen(true);
        } else {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        setBusy(false);
      }
    },
    [applyKey],
  );

  const onConfirmApply = useCallback(async () => {
    if (!pending) return;
    setBusy(true);
    setError(null);
    setErrorContext(panel === "settings-board" ? "settings" : "apply");
    try {
      setPlan(await pending.run(true));
      setConfirmOpen(false);
      setPending(null);
      setDryRunKey(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [pending, panel]);

  const filteredSettingsKeys = useMemo(() => {
    const keys = settings?.allowlist ?? [];
    const q = settingsQuery.trim().toLowerCase();
    return q ? keys.filter((k) => k.toLowerCase().includes(q)) : keys;
  }, [settings, settingsQuery]);

  const parseDraftValues = () => {
    const values: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(settingsDraft)) {
      if (v === "") continue;
      if (v === "true") values[k] = true;
      else if (v === "false") values[k] = false;
      else if (/^-?\d+$/.test(v)) values[k] = Number(v);
      else values[k] = v;
    }
    return values;
  };

  const back = (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={() => {
        setPanel("home");
        setPlan(null);
        setDryRunKey(null);
        setError(null);
      }}
    >
      Back to Command Center
    </Button>
  );

  const applyActions = (opts: {
    canDryRun: boolean;
    dryRun: () => void;
    apply: () => void;
    applyTestId?: string;
  }) => (
    <div className="cfg-actions">
      <Button
        type="button"
        variant="secondary"
        disabled={busy || !opts.canDryRun}
        onClick={opts.dryRun}
        data-testid="config-dry-run-btn"
      >
        {DRY_RUN_CTA}
      </Button>
      <Button
        type="button"
        variant="primary"
        disabled={busy || !canApply}
        onClick={opts.apply}
        data-testid={opts.applyTestId || "config-apply-btn"}
      >
        {primaryLabel}
      </Button>
      {unlockReason ? (
        <p className="cfg-primary-reason" data-testid="config-unlock-reason">
          {unlockReason}
        </p>
      ) : null}
    </div>
  );

  const linkCard = (card: RecipeCard, href: string, label: string) => (
    <div key={card.id} className="cfg-recipe" data-testid={`recipe-card-${card.id}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="cfg-recipe-name">{sanitizeConfigCopy(card.title)}</p>
          <p className="cfg-recipe-desc">{sanitizeConfigCopy(card.blurb)}</p>
        </div>
        <Badge variant="info">P1</Badge>
      </div>
      <div className="cfg-recipe-foot">
        <span className="text-xs text-muted">{sanitizeConfigCopy(card.clicks)}</span>
        <Link
          href={href}
          className="inline-flex h-8 items-center rounded-md border border-border-subtle bg-surface-raised px-3 text-xs font-semibold text-ink hover:border-accent/40"
        >
          {label}
        </Link>
      </div>
    </div>
  );

  return (
    <div className="mt-6" data-testid="config-command-center">
      <ConfigStageRail step={step} />

      <ConfigStateGuide
        className="mt-4"
        tone="warning"
        testId="config-honesty"
        guide={configHonestyGuide()}
      />

      {error ? (
        <ConfigErrorNotice
          className="mt-4"
          message={error}
          context={errorContext}
          onDismiss={() => setError(null)}
          onRetry={() => {
            if (panel === "home") void loadHome();
            else void openPanel(panel);
          }}
        />
      ) : null}

      {busy ? (
        <div className="cfg-progress" aria-busy="true" data-testid="config-progress" aria-live="polite">
          Working on {panel === "home" ? "recipes" : primaryLabel.toLowerCase()}…
        </div>
      ) : null}

      {panel === "home" ? (
        <>
          <div className="mb-4 mt-4">
            <h2 className="cfg-panel-title">Config Command Center</h2>
            <p className="cfg-panel-sub">
              Recipe-led setup: Day-1, <Term tech="ir.sequence">numbering</Term>, apps, import, and bulk in a few clicks.
            </p>
          </div>
          {listHydrated && cards.length === 0 ? (
            <ConfigStateGuide
              tone="accent"
              testId="config-empty-guide"
              guide={emptyConfigGuide()}
              actions={
                <Button type="button" size="sm" variant="secondary" onClick={() => void loadHome()}>
                  Reload recipes
                </Button>
              }
            />
          ) : null}
          {listHydrated && cards.length > 0 ? (
            <ConfigStateGuide tone="accent" testId="config-idle-guide" guide={idleConfigGuide()} />
          ) : null}
          {!listHydrated ? (
            <div className="cfg-progress mt-4" aria-busy="true" data-testid="config-recipes-loading">
              Loading recipes…
            </div>
          ) : (
            <div className="cfg-recipe-grid mt-4">
              {cards.map((card) => {
                if (card.id === "import-seeds") {
                  return linkCard(
                    card,
                    `/connections/${connectionId}/import?gallery=1`,
                    "Open Import",
                  );
                }
                if (card.id === "bulk-recipes") {
                  return linkCard(
                    card,
                    `/connections/${connectionId}/bulk-suite?recipes=1`,
                    "Open Bulk",
                  );
                }
                const map: Record<string, ConfigPanelId> = {
                  day1: "day1",
                  numbering: "numbering",
                  "apps-pack": "apps-pack",
                  "settings-board": "settings-board",
                  "multi-company": "multi-company",
                  "master-packs": "master-packs",
                };
                return (
                  <JobCard
                    key={card.id}
                    card={card}
                    onOpen={() => void openPanel(map[card.id] ?? "home")}
                  />
                );
              })}
            </div>
          )}
        </>
      ) : null}

      {panel === "day1" ? (
        <section className="cfg-panel" data-testid="day1-panel">
          {back}
          <h2 className="cfg-panel-title mt-3">Day-1 setup</h2>
          <p className="cfg-panel-sub">
            Company name, currency, country, language. Test run then {APPLY_CTA}.
          </p>
          <form
            className="mt-4 grid gap-3 sm:grid-cols-2"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              void runPlan("Day-1 setup", true, (confirmed) =>
                api.runDay1Setup(connectionId, {
                  name: day1.name,
                  currency_code: day1.currency_code,
                  country_code: day1.country_code || null,
                  language_code: day1.language_code || null,
                  email: day1.email || null,
                  phone: day1.phone || null,
                  dry_run: !confirmed,
                  confirm_advanced: confirmed,
                  confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                }),
              );
            }}
          >
            {(
              [
                ["name", "Company name"],
                ["currency_code", "Currency (USD)"],
                ["country_code", "Country (US)"],
                ["language_code", "Language (en_US)"],
                ["email", "Email"],
                ["phone", "Phone"],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="block text-sm">
                <span className="text-muted">{label}</span>
                <Input
                  className="mt-1"
                  value={day1[key]}
                  onChange={(e) => setDay1({ ...day1, [key]: e.target.value })}
                  required={key === "name"}
                />
              </label>
            ))}
            <div className="sm:col-span-2">
              {applyActions({
                canDryRun: Boolean(day1.name.trim()),
                dryRun: () =>
                  void runPlan("Day-1 setup", true, (confirmed) =>
                    api.runDay1Setup(connectionId, {
                      name: day1.name,
                      currency_code: day1.currency_code,
                      country_code: day1.country_code || null,
                      language_code: day1.language_code || null,
                      email: day1.email || null,
                      phone: day1.phone || null,
                      dry_run: !confirmed,
                      confirm_advanced: confirmed,
                      confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                    }),
                  ),
                apply: () =>
                  void runPlan("Day-1 setup", false, (confirmed) =>
                    api.runDay1Setup(connectionId, {
                      name: day1.name,
                      currency_code: day1.currency_code,
                      country_code: day1.country_code || null,
                      language_code: day1.language_code || null,
                      email: day1.email || null,
                      phone: day1.phone || null,
                      dry_run: false,
                      confirm_advanced: confirmed,
                      confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                    }),
                  ),
              })}
            </div>
          </form>
          <PlanPreview plan={plan} />
          {hasWriteResult ? (
            <ConfigStateGuide
              className="mt-4"
              tone="accent"
              testId="config-applied-guide"
              guide={appliedConfigGuide("Day-1 setup")}
            />
          ) : null}
        </section>
      ) : null}

      {panel === "numbering" ? (
        <section className="cfg-panel" data-testid="numbering-panel">
          {back}
          <h2 className="cfg-panel-title mt-3">Document <Term tech="ir.sequence">numbering</Term></h2>
          <p className="cfg-panel-sub">SO / INV / PO / payment prefixes as one pack.</p>
          <ul className="mt-4 space-y-2">
            {numberingCatalog.map((item) => {
              const checked = numberingKeys.includes(item.key);
              return (
                <li key={item.key}>
                  <label className="cfg-check-row">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() =>
                        setNumberingKeys((keys) =>
                          checked
                            ? keys.filter((k) => k !== item.key)
                            : [...keys, item.key],
                        )
                      }
                    />
                    <span>
                      <span className="font-medium text-ink">{item.name}</span>
                      <span className="mt-0.5 block font-mono text-xs text-muted">
                        {item.code} · {item.prefix} pad={item.padding}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
          {applyActions({
            canDryRun: numberingKeys.length > 0,
            dryRun: () =>
              void runPlan("Numbering pack", true, (confirmed) =>
                api.runNumberingPack(connectionId, {
                  keys: numberingKeys,
                  dry_run: true,
                  confirm_advanced: confirmed,
                  confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                }),
              ),
            apply: () =>
              void runPlan("Numbering pack", false, (confirmed) =>
                api.runNumberingPack(connectionId, {
                  keys: numberingKeys,
                  dry_run: false,
                  confirm_advanced: confirmed,
                  confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                }),
              ),
          })}
          <PlanPreview plan={plan} />
        </section>
      ) : null}

      {panel === "apps-pack" ? (
        <section className="cfg-panel" data-testid="apps-pack-panel">
          {back}
          <h2 className="cfg-panel-title mt-3">Apps pack installer</h2>
          <p className="cfg-panel-sub">Install a curated module set with dependency preview.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {appsPacks.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setSelectedPack(p.id)}
                className="cfg-pack"
                data-active={selectedPack === p.id ? "true" : "false"}
              >
                <p className="cfg-recipe-name">{sanitizeConfigCopy(p.title)}</p>
                <p className="cfg-recipe-desc">{sanitizeConfigCopy(p.blurb)}</p>
                <p className="mt-2 font-mono text-xs text-muted">{p.modules.join(", ")}</p>
              </button>
            ))}
          </div>
          {applyActions({
            canDryRun: Boolean(selectedPack),
            dryRun: () =>
              void runPlan("Apps pack", true, (confirmed) =>
                api.runAppsPack(connectionId, {
                  pack_id: selectedPack,
                  dry_run: true,
                  confirm_advanced: confirmed,
                  confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                }),
              ),
            apply: () =>
              void runPlan("Apps pack", false, (confirmed) =>
                api.runAppsPack(connectionId, {
                  pack_id: selectedPack,
                  dry_run: false,
                  confirm_advanced: confirmed,
                  confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                }),
              ),
          })}
          <PlanPreview plan={plan} />
        </section>
      ) : null}

      {panel === "settings-board" ? (
        <section className="cfg-panel" data-testid="settings-board-panel">
          {back}
          <h2 className="cfg-panel-title mt-3">Settings board</h2>
          <p className="cfg-panel-sub">
            Allowlisted res.config.settings. Search, edit, test run, then {PRIMARY_CTA}.
          </p>
          <Input
            className="mt-4 max-w-md"
            placeholder="Filter settings..."
            value={settingsQuery}
            onChange={(e) => setSettingsQuery(e.target.value)}
            data-testid="config-settings-filter"
          />
          <div className="cfg-settings-list">
            {filteredSettingsKeys.map((key) => (
              <label key={key} className="cfg-settings-row">
                <span className="font-mono text-xs text-ink">{key}</span>
                <Input
                  className="max-w-[12rem]"
                  value={settingsDraft[key] ?? ""}
                  onChange={(e) =>
                    setSettingsDraft((d) => ({ ...d, [key]: e.target.value }))
                  }
                />
              </label>
            ))}
            {!filteredSettingsKeys.length ? (
              <p className="text-xs text-muted">No allowlisted settings matched.</p>
            ) : null}
          </div>
          {applyActions({
            canDryRun: true,
            dryRun: () =>
              void runPlan(
                "Settings board",
                true,
                (confirmed) =>
                  api.patchSettingsBoard(connectionId, {
                    values: parseDraftValues(),
                    dry_run: true,
                    confirm_advanced: confirmed,
                    confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                  }),
                "settings",
              ),
            apply: () =>
              void runPlan(
                "Settings board",
                false,
                (confirmed) =>
                  api.patchSettingsBoard(connectionId, {
                    values: parseDraftValues(),
                    dry_run: false,
                    confirm_advanced: confirmed,
                    confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                  }),
                "settings",
              ),
            applyTestId: "config-save-setting-btn",
          })}
          <PlanPreview plan={plan} />
          {hasWriteResult ? (
            <ConfigStateGuide
              className="mt-4"
              tone="accent"
              testId="config-applied-guide"
              guide={appliedConfigGuide("Settings")}
            />
          ) : null}
        </section>
      ) : null}

      {panel === "multi-company" ? (
        <section className="cfg-panel" data-testid="multi-company-panel">
          {back}
          <h2 className="cfg-panel-title mt-3">Add company</h2>
          <p className="cfg-panel-sub">
            Create an additional res.company (users still need access).
          </p>
          <form
            className="mt-4 grid max-w-lg gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              void runPlan("Multi-company", true, (confirmed) =>
                api.runMultiCompany(connectionId, {
                  name: mc.name,
                  currency_code: mc.currency_code,
                  country_code: mc.country_code || null,
                  dry_run: true,
                  confirm_advanced: confirmed,
                  confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                }),
              );
            }}
          >
            <label className="block text-sm">
              <span className="text-muted">Company name</span>
              <Input
                className="mt-1"
                value={mc.name}
                onChange={(e) => setMc({ ...mc, name: e.target.value })}
                required
              />
            </label>
            <label className="block text-sm">
              <span className="text-muted">Currency</span>
              <Input
                className="mt-1"
                value={mc.currency_code}
                onChange={(e) => setMc({ ...mc, currency_code: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              <span className="text-muted">Country code</span>
              <Input
                className="mt-1"
                value={mc.country_code}
                onChange={(e) => setMc({ ...mc, country_code: e.target.value })}
              />
            </label>
            {applyActions({
              canDryRun: Boolean(mc.name.trim()),
              dryRun: () =>
                void runPlan("Multi-company", true, (confirmed) =>
                  api.runMultiCompany(connectionId, {
                    name: mc.name,
                    currency_code: mc.currency_code,
                    country_code: mc.country_code || null,
                    dry_run: true,
                    confirm_advanced: confirmed,
                    confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                  }),
                ),
              apply: () =>
                void runPlan("Multi-company", false, (confirmed) =>
                  api.runMultiCompany(connectionId, {
                    name: mc.name,
                    currency_code: mc.currency_code,
                    country_code: mc.country_code || null,
                    dry_run: false,
                    confirm_advanced: confirmed,
                    confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                  }),
                ),
            })}
          </form>
          <PlanPreview plan={plan} />
        </section>
      ) : null}

      {panel === "master-packs" ? (
        <section className="cfg-panel" data-testid="master-packs-panel">
          {back}
          <h2 className="cfg-panel-title mt-3">Master data packs</h2>
          <p className="cfg-panel-sub">UoM categories and fiscal position stubs.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {masterPacks.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setMasterId(p.id)}
                className="cfg-pack"
                data-active={masterId === p.id ? "true" : "false"}
              >
                <p className="cfg-recipe-name">{sanitizeConfigCopy(p.title)}</p>
                <p className="mt-1 font-mono text-xs text-muted">
                  {(p.categories || p.positions || []).join(", ")}
                </p>
              </button>
            ))}
          </div>
          {applyActions({
            canDryRun: Boolean(masterId),
            dryRun: () =>
              void runPlan("Master pack", true, (confirmed) =>
                api.runMasterPack(connectionId, {
                  pack_id: masterId,
                  dry_run: true,
                  confirm_advanced: confirmed,
                  confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                }),
              ),
            apply: () =>
              void runPlan("Master pack", false, (confirmed) =>
                api.runMasterPack(connectionId, {
                  pack_id: masterId,
                  dry_run: false,
                  confirm_advanced: confirmed,
                  confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                }),
              ),
          })}
          <PlanPreview plan={plan} />
        </section>
      ) : null}

      <ConfirmDialogV2
        open={confirmOpen}
        title={pending ? `Confirm: ${pending.label}` : "Confirm write"}
        warning="This writes to the live Odoo database. Type the confirmation phrase to continue. Test run never writes; this step does."
        risks={[
          "Changes apply on the connected Odoo instance",
          "Some steps may be hard to reverse without a snapshot",
          "Successful steps are not auto-undone",
        ]}
        phrase={CONFIRM_PHRASE}
        riskLevel="danger"
        busy={busy}
        onCancel={() => {
          setConfirmOpen(false);
          setPending(null);
        }}
        onConfirm={() => {
          void onConfirmApply();
        }}
      />
    </div>
  );
}
