"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import {
  api,
  AppTemplate,
  Connection,
  ConfirmationRequiredError,
  ScaffoldResult,
} from "@/lib/api";
import {
  scaffoldApplyAllowed,
  scaffoldApplyBlockedReason,
  scaffoldOptsFromSpec,
} from "@/lib/capabilities";

const CONFIRM_PHRASE = "I understand the risks";

const REUSE_SUGGESTIONS = [
  "res.partner",
  "res.users",
  "product.product",
  "account.move",
  "hr.employee",
];

const FALLBACK_TEMPLATES: AppTemplate[] = [
  {
    id: "library",
    name: "Library",
    description: "Books, authors, categories, and loans with member tracking.",
  },
  {
    id: "car_rental",
    name: "Car Rental",
    description:
      "Fleet, customers, contracts, rates, payments, damages & maintenance.",
  },
  {
    id: "crm_lite",
    name: "CRM Lite",
    description: "Lightweight leads with partner and stage.",
  },
  {
    id: "inventory_lite",
    name: "Inventory Lite",
    description: "Simple items with quantity and location.",
  },
];

export default function AppWizardPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [templates, setTemplates] = useState<AppTemplate[]>([]);
  const [selected, setSelected] = useState<AppTemplate | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [technicalPrefix, setTechnicalPrefix] = useState("");
  const [multiCompany, setMultiCompany] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScaffoldResult | null>(null);

  const [nlPrompt, setNlPrompt] = useState("");
  const [aiDraft, setAiDraft] = useState<Record<string, unknown> | null>(null);
  const [aiNote, setAiNote] = useState<string | null>(null);
  const [aiWarnings, setAiWarnings] = useState<string[]>([]);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [ollamaDetail, setOllamaDetail] = useState<string | null>(null);
  const [reuseModels, setReuseModels] = useState<string[]>(["res.partner"]);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [genUiConfirmOpen, setGenUiConfirmOpen] = useState(false);
  const [genUiResult, setGenUiResult] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);

      function withTimeout<T>(p: Promise<T>, ms: number, fallback: T): Promise<T> {
        return new Promise((resolve) => {
          const t = setTimeout(() => resolve(fallback), ms);
          p.then((v) => {
            clearTimeout(t);
            resolve(v);
          }).catch(() => {
            clearTimeout(t);
            resolve(fallback);
          });
        });
      }

      try {
        // Never block the whole wizard on slow Odoo/AI status (RAG used to
        // load MiniLM inside /ai/status and freeze "Loading templates…").
        const [conn, tpls, status, models] = await Promise.all([
          withTimeout(api.getConnection(connectionId), 8000, null as Connection | null),
          withTimeout(api.listAppTemplates(), 5000, FALLBACK_TEMPLATES),
          withTimeout(api.aiStatus().catch(() => null), 4000, null),
          withTimeout(
            api.listModels(connectionId, false).catch(() => []),
            6000,
            [],
          ),
        ]);
        if (cancelled) return;
        if (!conn) {
          setError("Could not load connection (timeout or API down). Templates still available.");
        } else {
          setConnection(conn);
        }
        setTemplates(tpls.length ? tpls : FALLBACK_TEMPLATES);
        setAiEnabled(Boolean(status?.enabled));
        setAvailableModels(
          (models || []).map((m) => m.model).filter(Boolean).slice(0, 400),
        );
        if (status?.ollama_reachable === false && status.ollama_detail) {
          setOllamaDetail(status.ollama_detail);
        } else if (status?.ollama_reachable === true) {
          setOllamaDetail(null);
        } else if (status?.ollama_detail) {
          setOllamaDetail(status.ollama_detail);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load");
          setTemplates(FALLBACK_TEMPLATES);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [connectionId]);

  function openConfirm(tpl: AppTemplate) {
    setSelected(tpl);
    setResult(null);
    setError(null);
    if (!displayName.trim()) {
      setDisplayName(tpl.name);
    }
    setConfirmOpen(true);
  }

  async function onConfirmScaffold(phrase: string) {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const prefix = technicalPrefix.trim();
      const res = await api.scaffoldApp(connectionId, {
        template_id: selected.id,
        display_name: displayName.trim() || selected.name,
        ...(prefix ? { technical_prefix: prefix } : {}),
        multi_company: selected.id === "library" ? multiCompany : false,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setResult(res);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Scaffold failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function onDraftFromPrompt() {
    setAiBusy(true);
    setError(null);
    setAiNote(null);
    setAiWarnings([]);
    setGenUiResult(null);
    try {
      const res = await api.draftModuleFromPrompt(nlPrompt.trim(), {
        connection_id: connectionId,
        reuse_models: reuseModels,
      });
      setAiDraft(res.draft);
      setAiNote(res.note ?? "Draft only — does not apply.");
      setAiWarnings(res.warnings ?? []);
    } catch (err) {
      setAiDraft(null);
      setError(err instanceof Error ? err.message : "AI draft failed");
      setAiNote(
        "Use Car Rental / Library template below if Ollama is unavailable. " +
          "Domain prompts like “car rental” still work offline via curated packs.",
      );
    } finally {
      setAiBusy(false);
    }
  }

  async function onGenerateUiFromDraft(phrase: string) {
    if (!aiDraft) return;
    setBusy(true);
    setError(null);
    setGenUiResult(null);
    try {
      const res = await api.applyModuleSpec(connectionId, {
        spec: aiDraft,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setGenUiConfirmOpen(false);
      setGenUiResult(res.message);
      setAiNote(
        `${res.message} · ${res.smart_buttons} smart button(s). ` +
          "Open Odoo app switcher or Designer to polish.",
      );
      if (res.warnings?.length) setAiWarnings(res.warnings);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Generate UI failed");
      }
    } finally {
      setBusy(false);
    }
  }

  function toggleReuse(model: string) {
    setReuseModels((prev) =>
      prev.includes(model) ? prev.filter((m) => m !== model) : [...prev, model],
    );
  }

  /** Library scaffold creates an object_write loan automation. */
  function templateScaffoldOpts(tplId: string) {
    return tplId === "library" ? { requireObjectWrite: true as const } : {};
  }

  const draftOpts = scaffoldOptsFromSpec(
    aiDraft as Record<string, unknown> | null,
  );
  const canGenerateUi = scaffoldApplyAllowed(connection, draftOpts);
  const generateUiBlocked = scaffoldApplyBlockedReason(connection, draftOpts);

  async function onExportLibraryWithFines() {
    setBusy(true);
    setError(null);
    try {
      const mod = await api.exportLibraryModule({
        technical_name: "library_mgmt",
        display_name: displayName.trim() || "Library Management",
        fines: true,
        reminders: true,
        multi_company: multiCompany,
      });
      const bin = Uint8Array.from(atob(mod.content_base64), (c) =>
        c.charCodeAt(0),
      );
      const blob = new Blob([bin], { type: "application/zip" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = mod.filename;
      a.click();
      URL.revokeObjectURL(url);
      setAiNote(mod.note);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#3d2a38_0%,_#1a1218_50%,_#0c090b_100%)] px-6 py-10 text-[#f4eef2]">
      <div className="mx-auto max-w-4xl">
        <div className="flex flex-wrap gap-4 text-sm">
          <Link
            href={`/connections/${connectionId}`}
            className="text-[#c9a9c0] hover:underline"
          >
            ← Metadata
          </Link>
          <Link
            href={`/connections/${connectionId}/builder`}
            className="text-[#8f7a88] hover:underline"
          >
            Builder
          </Link>
          <Link
            href={`/connections/${connectionId}/designer`}
            className="text-[#8f7a88] hover:underline"
          >
            Designer
          </Link>
          <Link
            href={`/connections/${connectionId}/reminders`}
            className="text-[#8f7a88] hover:underline"
          >
            Reminders
          </Link>
        </div>

        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          App wizard
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]">
          {connection
            ? `${connection.name} · scaffold a starter app onto this Odoo`
            : connectionId}
        </p>
        <VersionAwarenessBanner capabilities={connection?.capabilities} />

        <label className="mt-6 block max-w-md text-sm">
          <span className="text-[#a8909e]">Display name</span>
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="e.g. Acme Library"
            className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
          />
        </label>

        <label className="mt-4 block max-w-md text-sm">
          <span className="text-[#a8909e]">Technical prefix (optional)</span>
          <input
            value={technicalPrefix}
            onChange={(e) => setTechnicalPrefix(e.target.value)}
            placeholder="e.g. lib_demo → x_lib_demo_book"
            className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
          />
          <span className="mt-0.5 block text-xs text-[#8f7a88]">
            Omit for fixed template model names (library: x_lib_book, …).
          </span>
        </label>

        <label className="mt-4 flex max-w-md items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={multiCompany}
            onChange={(e) => setMultiCompany(e.target.checked)}
            className="mt-1"
          />
          <span>
            <span className="text-[#a8909e]">Multi-company aware</span>
            <span className="mt-0.5 block text-xs text-[#8f7a88]">
              Applies when you scaffold or export the <strong>Library</strong> template
              only. CRM Lite / Inventory Lite ignore this checkbox today. Adds a company
              field + record rules so each Odoo company sees its own catalog/loans.
              Requires companies configured under Odoo Settings.
            </span>
          </span>
        </label>

        <section className="mt-8 border border-[#3d2a38] bg-[#0f1a16]/70 p-5">
          <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">
            Describe your app
          </h2>
          <p className="mt-1 text-sm text-[#8f7a88]">
            NL → robust ModuleSpec via Ollama ({aiEnabled ? "enabled" : "off"}
            {ollamaDetail ? ` · ${ollamaDetail}` : ""}). Domain packs (e.g. car
            rental) expand thin prompts even when AI is off. Draft never applies
            until you click Generate UI.
          </p>
          <textarea
            value={nlPrompt}
            onChange={(e) => setNlPrompt(e.target.value)}
            rows={3}
            placeholder="Car rental fleet: vehicles, contracts, deposits, overdue returns…"
            className="mt-3 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
          />

          <div className="mt-4">
            <p className="text-xs uppercase tracking-wide text-[#8f7a88]">
              Reuse existing Odoo models
            </p>
            <p className="mt-1 text-xs text-[#8f7a88]">
              Link these instead of inventing duplicates (Contacts, products, invoices…).
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {REUSE_SUGGESTIONS.map((m) => {
                const on = reuseModels.includes(m);
                return (
                  <button
                    key={m}
                    type="button"
                    onClick={() => toggleReuse(m)}
                    className={`border px-2 py-1 font-mono text-xs ${
                      on
                        ? "border-[#c9a9c0] bg-[#1a1218] text-[#c9a9c0]"
                        : "border-[#3d2a38] text-[#8f7a88] hover:border-[#4a3550]"
                    }`}
                  >
                    {on ? "✓ " : ""}
                    {m}
                  </button>
                );
              })}
            </div>
            {availableModels.length > 0 && (
              <label className="mt-3 block text-xs text-[#8f7a88]">
                Or pick from this connection
                <select
                  className="mt-1 w-full max-w-md border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-xs text-[#f4eef2]"
                  defaultValue=""
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v) toggleReuse(v);
                    e.target.value = "";
                  }}
                >
                  <option value="">Add model…</option>
                  {availableModels
                    .filter((m) => !REUSE_SUGGESTIONS.includes(m))
                    .slice(0, 200)
                    .map((m) => (
                      <option key={m} value={m}>
                        {m}
                        {reuseModels.includes(m) ? " ✓" : ""}
                      </option>
                    ))}
                </select>
              </label>
            )}
            {reuseModels.length > 0 && (
              <p className="mt-2 font-mono text-xs text-[#c9a9c0]">
                Selected: {reuseModels.join(", ")}
              </p>
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-3">
            <button
              type="button"
              disabled={aiBusy || nlPrompt.trim().length < 3}
              onClick={() => onDraftFromPrompt()}
              className="border border-[#c9a9c0] px-3 py-1.5 text-sm text-[#c9a9c0] disabled:opacity-50"
            >
              {aiBusy ? "Drafting…" : "Draft ModuleSpec"}
            </button>
            <button
              type="button"
              disabled={!aiDraft || busy || !canGenerateUi}
              title={generateUiBlocked ?? undefined}
              onClick={() => setGenUiConfirmOpen(true)}
              className="border border-[#c9a96e] px-3 py-1.5 text-sm text-[#c9a96e] disabled:opacity-50"
            >
              Generate UI from JSON
            </button>
            <button
              type="button"
              disabled={!aiDraft}
              onClick={() => {
                if (!aiDraft) return;
                const modelCount = Array.isArray(aiDraft.models)
                  ? aiDraft.models.length
                  : 0;
                if (modelCount === 0) {
                  setError(
                    "Draft has 0 models — Draft ModuleSpec again before opening the builder.",
                  );
                  return;
                }
                try {
                  sessionStorage.setItem(
                    `modulespec-draft:${connectionId}`,
                    JSON.stringify(aiDraft),
                  );
                } catch {
                  setError("Could not store draft in this browser session.");
                  return;
                }
                window.location.href = `/connections/${connectionId}/modulespec`;
              }}
              className="border border-[#c9a9c0] px-3 py-1.5 text-sm text-[#c9a9c0] disabled:opacity-50"
            >
              Open in ModuleSpec builder
            </button>
            <button
              type="button"
              onClick={() => {
                setAiDraft(null);
                setNlPrompt("");
                setAiWarnings([]);
                setAiNote("Use a template card below.");
              }}
              className="text-sm text-[#8f7a88] hover:underline"
            >
              Clear draft
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => onExportLibraryWithFines()}
              className="text-sm text-[#c9a9c0] hover:underline disabled:opacity-50"
            >
              Export library zip (fines=true)
            </button>
          </div>
          {aiDraft && generateUiBlocked && (
            <p className="mt-3 text-sm text-[#e8d09f]">{generateUiBlocked}</p>
          )}
          {aiNote && <p className="mt-3 text-sm text-[#c9a9c0]">{aiNote}</p>}
          {genUiResult && (
            <p className="mt-2 text-sm text-[#c9a96e]">{genUiResult}</p>
          )}
          {aiWarnings.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-[#f0c090]">
              {aiWarnings.slice(0, 12).map((w, i) => (
                <li key={`${i}-${w}`}>{w}</li>
              ))}
            </ul>
          )}
          {aiDraft && (
            <>
              <p className="mt-3 text-xs text-[#8f7a88]">
                {Array.isArray(aiDraft.models) ? aiDraft.models.length : "?"} models
                · {Array.isArray(aiDraft.views) ? aiDraft.views.length : 0} views
                ·{" "}
                {Array.isArray(aiDraft.smart_buttons)
                  ? aiDraft.smart_buttons.length
                  : 0}{" "}
                smart buttons
                {typeof aiDraft.domain_pack === "string"
                  ? ` · pack: ${aiDraft.domain_pack}`
                  : ""}
              </p>
              <pre className="mt-2 max-h-64 overflow-auto border border-[#1e2f29] bg-[#0c090b] p-3 text-xs text-[#d4c4ce]">
                {JSON.stringify(aiDraft, null, 2)}
              </pre>
            </>
          )}
        </section>

        {loading && <p className="mt-4 text-sm text-[#8f7a88]">Loading templates…</p>}
        {error && <p className="mt-4 text-sm text-[#f0a8a0]">{error}</p>}

        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {templates.map((tpl) => {
            const active = selected?.id === tpl.id;
            const opts = templateScaffoldOpts(tpl.id);
            const canScaffold = scaffoldApplyAllowed(connection, opts);
            const blocked = scaffoldApplyBlockedReason(connection, opts);
            return (
              <button
                key={tpl.id}
                type="button"
                data-testid={`template-card-${tpl.id}`}
                disabled={!canScaffold}
                title={blocked ?? undefined}
                onClick={() => {
                  if (!canScaffold) return;
                  openConfirm(tpl);
                }}
                className={`border p-4 text-left transition ${
                  !canScaffold
                    ? "cursor-not-allowed border-[#3d2a38] bg-[#0f1a16]/40 opacity-50"
                    : active
                      ? "border-[#c9a9c0] bg-[#1a1218]"
                      : "border-[#3d2a38] bg-[#0f1a16]/60 hover:border-[#4a3550]"
                }`}
              >
                <p className="font-[family-name:var(--font-display)] text-lg text-[#faf6f9]">
                  {tpl.name}
                </p>
                <p className="mt-1 font-mono text-xs text-[#c9a9c0]">{tpl.id}</p>
                <p className="mt-2 text-sm text-[#8f7a88]">{tpl.description}</p>
                {blocked && (
                  <p className="mt-2 text-xs text-[#e8d09f]">{blocked}</p>
                )}
              </button>
            );
          })}
        </div>

        {result && (
          <section
            data-testid="scaffold-result"
            className="mt-8 border border-[#3d2a38] bg-[#0f1a16]/70 p-5"
          >
            <h2 className="font-[family-name:var(--font-display)] text-xl text-[#faf6f9]">
              Scaffold result
            </h2>
            <p className="mt-2 text-sm text-[#c9a9c0]">
              {result.ok ? "OK" : "Partial"} · {result.message}
            </p>
            <p className="mt-1 text-sm text-[#8f7a88]">
              Template <code className="text-[#c9a9c0]">{result.template_id}</code> ·{" "}
              {result.fields_created} fields created
              {typeof result.view_injects === "number"
                ? ` · ${result.view_injects} view inject(s)`
                : ""}
            </p>
            {result.warnings && result.warnings.length > 0 && (
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-[#f0c090]">
                {result.warnings.map((w, i) => (
                  <li key={`${i}-${w}`}>{w}</li>
                ))}
              </ul>
            )}

            <ol
              data-testid="scaffold-checklist"
              className="mt-5 space-y-2 text-sm"
            >
              <li className="flex items-start gap-2 border border-[#1e2f29] px-3 py-2">
                <span
                  className={
                    result.models.length > 0 ? "text-[#c9a9c0]" : "text-[#8f7a88]"
                  }
                  aria-hidden
                >
                  {result.models.length > 0 ? "✓" : "○"}
                </span>
                <span>
                  Models created
                  {result.models.length > 0
                    ? ` (${result.models.length})`
                    : " — none reported"}
                  {result.models_skipped && result.models_skipped.length > 0
                    ? ` · skipped: ${result.models_skipped.join(", ")}`
                    : ""}
                </span>
              </li>
              <li className="flex items-start gap-2 border border-[#1e2f29] px-3 py-2">
                <span
                  className={
                    (result.menus_created ?? 0) > 0
                      ? "text-[#c9a9c0]"
                      : "text-[#8f7a88]"
                  }
                  aria-hidden
                >
                  {(result.menus_created ?? 0) > 0 ? "✓" : "○"}
                </span>
                <span>
                  Menus created
                  {typeof result.menus_created === "number"
                    ? ` (${result.menus_created})`
                    : " — n/a"}
                </span>
              </li>
              <li className="flex items-start gap-2 border border-[#1e2f29] px-3 py-2">
                <span className="text-[#c9a9c0]" aria-hidden>
                  →
                </span>
                <Link
                  href={
                    result.models[0]
                      ? `/connections/${connectionId}/designer?model=${encodeURIComponent(result.models[0])}`
                      : `/connections/${connectionId}/designer`
                  }
                  className="text-[#c9a9c0] hover:underline"
                >
                  Open designer
                </Link>
              </li>
              <li className="flex items-start gap-2 border border-[#1e2f29] px-3 py-2">
                <span className="text-[#c9a9c0]" aria-hidden>
                  →
                </span>
                <Link
                  href={`/connections/${connectionId}`}
                  className="text-[#c9a9c0] hover:underline"
                >
                  Run sandbox
                </Link>
                <span className="text-[#8f7a88]">(on connection page)</span>
              </li>
            </ol>

            <ul
              data-testid="scaffold-models"
              className="mt-4 space-y-2 text-sm"
            >
              {result.models.map((model) => (
                <li
                  key={model}
                  className="flex flex-wrap items-center gap-3 border border-[#1e2f29] px-3 py-2"
                >
                  <span className="font-mono text-[#c9a9c0]">{model}</span>
                  <Link
                    href={`/connections/${connectionId}/builder`}
                    className="text-xs text-[#c9a9c0] hover:underline"
                  >
                    Builder
                  </Link>
                  <Link
                    href={`/connections/${connectionId}/designer?model=${encodeURIComponent(model)}`}
                    className="text-xs text-[#c9a9c0] hover:underline"
                  >
                    Designer
                  </Link>
                </li>
              ))}
              {result.models.length === 0 && (
                <li className="text-[#8f7a88]">No models reported.</li>
              )}
            </ul>
            <div className="mt-4 flex flex-wrap gap-3 text-sm">
              <Link
                href={`/connections/${connectionId}`}
                className="border border-[#c9a9c0] px-3 py-1.5 text-[#c9a9c0]"
              >
                Back to connection
              </Link>
              <Link
                href={`/connections/${connectionId}/builder`}
                className="bg-[#714B67] px-3 py-1.5 font-semibold text-white"
              >
                Open builder
              </Link>
            </div>
          </section>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title={`Scaffold ${selected?.name ?? "app"}`}
        warning="This creates models, fields, and views on the live Odoo connection."
        risks={[
          "Live metadata writes on this connection",
          "May create multiple x_* models and ACL rows",
          "Existing models with the same name are skipped or extended",
          ...(selected?.id === "library" && multiCompany
            ? ["Adds x_company_id + multi-company record rules"]
            : []),
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={onConfirmScaffold}
      />
      <ConfirmDialog
        open={genUiConfirmOpen}
        title="Generate UI from JSON"
        warning="Applies the ModuleSpec draft: models, fields, views, menus, and smart buttons on this live Odoo connection."
        risks={[
          "Creates ir.model / fields / views / menus",
          "May rewrite primary form arches for custom x_* models (statusbars)",
          "Smart buttons use inherit views — stock forms like Contacts stay intact",
          "Automations in the draft are listed only — create them on Automations page",
          "Prefer a sandbox connection before production",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setGenUiConfirmOpen(false)}
        onConfirm={onGenerateUiFromDraft}
      />
    </main>
  );
}
