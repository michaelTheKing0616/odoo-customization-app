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
import { Callout } from "@/components/ui/Callout";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/layout-primitives";

const CONFIRM_PHRASE = "I understand the risks";

type PanelId =
  | "home"
  | "day1"
  | "numbering"
  | "apps-pack"
  | "settings-board"
  | "multi-company"
  | "master-packs";

type PendingApply = {
  label: string;
  run: (confirmed: boolean) => Promise<RecipePlanOut>;
};

function PlanPreview({ plan }: { plan: RecipePlanOut | null }) {
  if (!plan) return null;
  return (
    <Callout
      variant="info"
      title={plan.dry_run ? "Dry-run plan" : "Applied"}
      className="mt-4"
      testId="recipe-plan-preview"
    >
      <p className="text-sm">
        {plan.message || (plan.dry_run ? "Review steps, then Apply." : "Done.")}
      </p>
      {plan.warnings?.length ? (
        <ul className="mt-2 list-disc pl-4 text-xs text-muted">
          {plan.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}
      <ul className="mt-3 space-y-1 text-xs text-muted">
        {plan.steps.map((s, i) => (
          <li key={`${s.op}-${s.target}-${i}`}>
            <span className="font-mono text-ink">{s.op}</span> · {s.target} — {s.detail}
          </li>
        ))}
      </ul>
      {plan.applied?.length ? (
        <p className="mt-2 text-xs text-ink">{plan.applied.join(" · ")}</p>
      ) : null}
    </Callout>
  );
}

function JobCard({ card, onOpen }: { card: RecipeCard; onOpen: () => void }) {
  const phaseVariant =
    card.phase === "p0" ? "success" : card.phase === "p1" ? "info" : "default";
  return (
    <Card
      className="flex flex-col gap-3 p-4 transition hover:border-accent/40"
      data-testid={`recipe-card-${card.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-ui-title text-ink">{card.title}</p>
          <p className="mt-1 text-sm text-muted">{card.blurb}</p>
        </div>
        <Badge variant={phaseVariant as "success" | "info" | "default"}>
          {card.phase.toUpperCase()}
        </Badge>
      </div>
      <div className="mt-auto flex items-center justify-between gap-2">
        <span className="text-xs text-muted">{card.clicks}</span>
        <Button type="button" size="sm" variant="primary" onClick={onOpen}>
          Open
        </Button>
      </div>
    </Card>
  );
}

export export function ConfigCommandCenter({ connectionId }: { connectionId: string }) {
  const [cards, setCards] = useState<RecipeCard[]>([]);
  const [panel, setPanel] = useState<PanelId>("home");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState<RecipePlanOut | null>(null);
  const [pending, setPending] = useState<PendingApply | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

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

  const loadHome = useCallback(async () => {
    try {
      setCards(await api.listConfigRecipes(connectionId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [connectionId]);

  useEffect(() => {
    void loadHome();
  }, [loadHome]);

  const openPanel = useCallback(
    async (id: PanelId) => {
      setPanel(id);
      setPlan(null);
      setError(null);
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

  const runConfirmed = useCallback(
    async (label: string, run: (confirmed: boolean) => Promise<RecipePlanOut>) => {
      setBusy(true);
      setError(null);
      try {
        setPlan(await run(false));
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
    [],
  );

  const onConfirmApply = useCallback(async () => {
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      setPlan(await pending.run(true));
      setConfirmOpen(false);
      setPending(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [pending]);

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
      }}
    >
      ← Command Center
    </Button>
  );

  const linkCard = (card: RecipeCard, href: string, label: string) => (
    <Card
      key={card.id}
      className="flex flex-col gap-3 p-4"
      data-testid={`recipe-card-${card.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-ui-title text-ink">{card.title}</p>
          <p className="mt-1 text-sm text-muted">{card.blurb}</p>
        </div>
        <Badge variant="info">P1</Badge>
      </div>
      <div className="mt-auto flex items-center justify-between gap-2">
        <span className="text-xs text-muted">{card.clicks}</span>
        <Link
          href={href}
          className="inline-flex h-8 items-center rounded-md bg-accent px-3 text-xs font-semibold text-white"
        >
          {label}
        </Link>
      </div>
    </Card>
  );

  return (
    <div className="mt-6" data-testid="config-command-center">
      {error ? <ErrorNotice message={error} className="mb-4" /> : null}

      {panel === "home" ? (
        <>
          <div className="mb-4">
            <h2 className="text-ui-title text-ink">Config Command Center</h2>
            <p className="mt-1 text-sm text-muted">
              Recipe-led setup — Day-1, numbering, apps, import, and bulk in a few clicks.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
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
              const map: Record<string, PanelId> = {
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
        </>
      ) : null}

      {panel === "day1" ? (
        <section data-testid="day1-panel">
          {back}
          <h2 className="mt-3 text-ui-title">Day-1 setup</h2>
          <p className="mt-1 text-sm text-muted">
            Company name, currency, country, language — dry-run then apply.
          </p>
          <form
            className="mt-4 grid gap-3 sm:grid-cols-2"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              void runConfirmed("Day-1 setup", (confirmed) =>
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
            <div className="flex flex-wrap gap-2 sm:col-span-2">
              <Button type="submit" variant="secondary" disabled={busy || !day1.name.trim()}>
                Dry-run
              </Button>
              <Button
                type="button"
                variant="primary"
                disabled={busy || !day1.name.trim()}
                onClick={() =>
                  void runConfirmed("Day-1 setup", (confirmed) =>
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
                  )
                }
              >
                Apply
              </Button>
            </div>
          </form>
          <PlanPreview plan={plan} />
        </section>
      ) : null}

      {panel === "numbering" ? (
        <section data-testid="numbering-panel">
          {back}
          <h2 className="mt-3 text-ui-title">Document numbering</h2>
          <p className="mt-1 text-sm text-muted">SO / INV / PO / payment prefixes as one pack.</p>
          <ul className="mt-4 space-y-2">
            {numberingCatalog.map((item) => {
              const checked = numberingKeys.includes(item.key);
              return (
                <li key={item.key}>
                  <label className="flex items-start gap-3 rounded-md border border-border-subtle bg-surface p-3 text-sm">
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
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={busy || !numberingKeys.length}
              onClick={() =>
                void runConfirmed("Numbering pack", (confirmed) =>
                  api.runNumberingPack(connectionId, {
                    keys: numberingKeys,
                    dry_run: true,
                    confirm_advanced: confirmed,
                    confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                  }),
                )
              }
            >
              Dry-run
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={busy || !numberingKeys.length}
              onClick={() =>
                void runConfirmed("Numbering pack", (confirmed) =>
                  api.runNumberingPack(connectionId, {
                    keys: numberingKeys,
                    dry_run: false,
                    confirm_advanced: confirmed,
                    confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                  }),
                )
              }
            >
              Apply pack
            </Button>
          </div>
          <PlanPreview plan={plan} />
        </section>
      ) : null}

      {panel === "apps-pack" ? (
        <section data-testid="apps-pack-panel">
          {back}
          <h2 className="mt-3 text-ui-title">Apps pack installer</h2>
          <p className="mt-1 text-sm text-muted">
            Install a curated module set with dependency preview.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {appsPacks.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setSelectedPack(p.id)}
                className={`rounded-md border p-4 text-left text-sm transition ${
                  selectedPack === p.id
                    ? "border-accent bg-accent/5"
                    : "border-border-subtle bg-surface hover:border-accent/40"
                }`}
              >
                <p className="font-medium text-ink">{p.title}</p>
                <p className="mt-1 text-xs text-muted">{p.blurb}</p>
                <p className="mt-2 font-mono text-xs text-muted">{p.modules.join(", ")}</p>
              </button>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={busy || !selectedPack}
              onClick={() =>
                void runConfirmed("Apps pack", (confirmed) =>
                  api.runAppsPack(connectionId, {
                    pack_id: selectedPack,
                    dry_run: true,
                    confirm_advanced: confirmed,
                    confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                  }),
                )
              }
            >
              Preview deps
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={busy || !selectedPack}
              onClick={() =>
                void runConfirmed("Apps pack", (confirmed) =>
                  api.runAppsPack(connectionId, {
                    pack_id: selectedPack,
                    dry_run: false,
                    confirm_advanced: confirmed,
                    confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                  }),
                )
              }
            >
              Install pack
            </Button>
          </div>
          <PlanPreview plan={plan} />
        </section>
      ) : null}

      {panel === "settings-board" ? (
        <section data-testid="settings-board-panel">
          {back}
          <h2 className="mt-3 text-ui-title">Settings board</h2>
          <p className="mt-1 text-sm text-muted">
            Allowlisted res.config.settings — search, edit, dry-run, apply.
          </p>
          <Input
            className="mt-4 max-w-md"
            placeholder="Filter settings…"
            value={settingsQuery}
            onChange={(e) => setSettingsQuery(e.target.value)}
          />
          <div className="mt-4 max-h-80 space-y-2 overflow-auto rounded-md border border-border-subtle p-3">
            {filteredSettingsKeys.map((key) => (
              <label key={key} className="flex items-center justify-between gap-3 text-sm">
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
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={busy}
              onClick={() =>
                void runConfirmed("Settings board", (confirmed) =>
                  api.patchSettingsBoard(connectionId, {
                    values: parseDraftValues(),
                    dry_run: true,
                    confirm_advanced: confirmed,
                    confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                  }),
                )
              }
            >
              Dry-run
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={busy}
              onClick={() =>
                void runConfirmed("Settings board", (confirmed) =>
                  api.patchSettingsBoard(connectionId, {
                    values: parseDraftValues(),
                    dry_run: false,
                    confirm_advanced: confirmed,
                    confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                  }),
                )
              }
            >
              Apply settings
            </Button>
          </div>
          <PlanPreview plan={plan} />
        </section>
      ) : null}

      {panel === "multi-company" ? (
        <section data-testid="multi-company-panel">
          {back}
          <h2 className="mt-3 text-ui-title">Add company</h2>
          <p className="mt-1 text-sm text-muted">
            Create an additional res.company (users still need access).
          </p>
          <form
            className="mt-4 grid max-w-lg gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              void runConfirmed("Multi-company", (confirmed) =>
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
            <div className="flex flex-wrap gap-2">
              <Button type="submit" variant="secondary" disabled={busy || !mc.name.trim()}>
                Dry-run
              </Button>
              <Button
                type="button"
                variant="primary"
                disabled={busy || !mc.name.trim()}
                onClick={() =>
                  void runConfirmed("Multi-company", (confirmed) =>
                    api.runMultiCompany(connectionId, {
                      name: mc.name,
                      currency_code: mc.currency_code,
                      country_code: mc.country_code || null,
                      dry_run: false,
                      confirm_advanced: confirmed,
                      confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                    }),
                  )
                }
              >
                Create company
              </Button>
            </div>
          </form>
          <PlanPreview plan={plan} />
        </section>
      ) : null}

      {panel === "master-packs" ? (
        <section data-testid="master-packs-panel">
          {back}
          <h2 className="mt-3 text-ui-title">Master data packs</h2>
          <p className="mt-1 text-sm text-muted">UoM categories and fiscal position stubs.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {masterPacks.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setMasterId(p.id)}
                className={`rounded-md border p-4 text-left text-sm ${
                  masterId === p.id
                    ? "border-accent bg-accent/5"
                    : "border-border-subtle bg-surface"
                }`}
              >
                <p className="font-medium text-ink">{p.title}</p>
                <p className="mt-1 font-mono text-xs text-muted">
                  {(p.categories || p.positions || []).join(", ")}
                </p>
              </button>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={busy}
              onClick={() =>
                void runConfirmed("Master pack", (confirmed) =>
                  api.runMasterPack(connectionId, {
                    pack_id: masterId,
                    dry_run: true,
                    confirm_advanced: confirmed,
                    confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                  }),
                )
              }
            >
              Dry-run
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={busy}
              onClick={() =>
                void runConfirmed("Master pack", (confirmed) =>
                  api.runMasterPack(connectionId, {
                    pack_id: masterId,
                    dry_run: false,
                    confirm_advanced: confirmed,
                    confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
                  }),
                )
              }
            >
              Apply pack
            </Button>
          </div>
          <PlanPreview plan={plan} />
        </section>
      ) : null}

      <ConfirmDialogV2
        open={confirmOpen}
        title={pending ? `Confirm: ${pending.label}` : "Confirm write"}
        warning="This writes to the live Odoo database. Type the confirmation phrase to continue."
        risks={[
          "Changes apply on the connected Odoo instance",
          "Some steps may be hard to reverse without a snapshot",
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
