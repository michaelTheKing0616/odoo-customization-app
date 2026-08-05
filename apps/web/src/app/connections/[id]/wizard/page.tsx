"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { SuggestTemplateButton } from "@/components/SuggestTemplateButton";
import { SaveAsComponentButton } from "@/components/SaveAsComponentButton";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import {
  api,
  AppTemplate,
  Connection,
  ConfirmationRequiredError,
  ProtectedModuleRefusal,
  ScaffoldResult,
} from "@/lib/api";
import {
  scaffoldApplyAllowed,
  scaffoldApplyBlockedReason,
  scaffoldOptsFromSpec,
} from "@/lib/capabilities";
import { AskWhyButton } from "@/components/expert/AskWhyButton";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { reportApiError } from "@/lib/api-error";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card, PageHeader, Skeleton } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { Badge } from "@/components/ui/Badge";
import { CodeBlock } from "@/components/ui/CodeBlock";

const CONFIRM_PHRASE = "I understand the risks";

const PIPELINE_STEPS = [
  "Entities",
  "Fields",
  "Relationships",
  "Workflow",
  "Automations",
  "Views",
] as const;

function pipelineStepIndex(draft: Record<string, unknown> | null): number {
  if (!draft) return 0;
  if (Array.isArray(draft.views) && draft.views.length > 0) return 5;
  if (Array.isArray(draft.automations) && draft.automations.length > 0) return 4;
  if (draft.workflow || draft.states) return 3;
  if (Array.isArray(draft.models) && draft.models.length > 1) return 2;
  if (Array.isArray(draft.models) && draft.models.length > 0) return 1;
  return 0;
}

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

function dedupeTemplates(templates: AppTemplate[]): AppTemplate[] {
  const seen = new Set<string>();
  return templates.filter((tpl) => {
    if (seen.has(tpl.id)) return false;
    seen.add(tpl.id);
    return true;
  });
}

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
  const draftSummary = aiDraft
    ? String(aiDraft.display_name ?? aiDraft.technical_name ?? "draft")
    : undefined;
  useSyncShellContext({ draftSummary });
  const [aiNote, setAiNote] = useState<string | null>(null);
  const [aiWarnings, setAiWarnings] = useState<string[]>([]);
  const draftNeedsRegenerate = Boolean(
    aiDraft &&
      ((aiDraft._depth as { seeded?: boolean } | undefined)?.seeded ||
        aiWarnings.some(
          (w) =>
            w.includes("field-deepen skipped") ||
            w.includes("depth met via generic seeds"),
        )),
  );
  const [aiRefusals, setAiRefusals] = useState<ProtectedModuleRefusal[]>([]);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [ollamaDetail, setOllamaDetail] = useState<string | null>(null);
  const [reuseModels, setReuseModels] = useState<string[]>(["res.partner"]);
  const [rejectedInferredReuse, setRejectedInferredReuse] = useState<string[]>([]);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [genUiConfirmOpen, setGenUiConfirmOpen] = useState(false);
  const [genUiResult, setGenUiResult] = useState<string | null>(null);
  const [validateLiveResult, setValidateLiveResult] = useState<
    import("@/lib/api").ValidateLiveResult | null
  >(null);
  const [skipValidateLive, setSkipValidateLive] = useState(false);
  const [grainLabel, setGrainLabel] = useState<string | null>(null);
  const [grainOverride, setGrainOverride] = useState<string>("");
  const [connectPoints, setConnectPoints] = useState<Record<string, unknown> | null>(null);
  const [hostCandidates, setHostCandidates] = useState<
    Array<{ model: string; label: string; score: number; reason?: string }>
  >([]);
  const [componentGallery, setComponentGallery] = useState<
    Array<{ id: string; name: string; description: string; host_slot: string }>
  >([]);
  const [selectedGalleryId, setSelectedGalleryId] = useState("");
  const [connectPointsApproved, setConnectPointsApproved] = useState(false);
  const [connectReviewBusy, setConnectReviewBusy] = useState(false);
  const [effectiveGrain, setEffectiveGrain] = useState<string>("");
  const [overlapFindings, setOverlapFindings] = useState<
    Array<{
      id: string;
      title: string;
      evidence: string;
      deep_link?: string | null;
      extend_host_model?: string | null;
    }>
  >([]);
  const [overlapChoice, setOverlapChoice] = useState<string | null>(null);
  const [overlapFindingId, setOverlapFindingId] = useState<string | null>(null);
  const [overlapBusy, setOverlapBusy] = useState(false);

  const resolvedGrain = grainOverride || effectiveGrain;
  const isFullAppGrain =
    resolvedGrain === "full_app" || grainLabel?.toLowerCase() === "full app";
  const isComponentGrain =
    !isFullAppGrain &&
    (resolvedGrain === "feature_slice" || resolvedGrain === "field_pack");
  const needsConnectReview = isComponentGrain;
  const overlapResolved =
    overlapFindings.length === 0 || overlapChoice === "build_anyway" || overlapChoice === "use";
  const canDraftModule =
    nlPrompt.trim().length >= 3 &&
    overlapResolved &&
    (!needsConnectReview || (connectPointsApproved && connectPoints !== null));

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
        const [conn, tpls, status, models, gallery] = await Promise.all([
          withTimeout(api.getConnection(connectionId), 8000, null as Connection | null),
          withTimeout(api.listAppTemplates(), 5000, FALLBACK_TEMPLATES),
          withTimeout(api.aiStatus().catch(() => null), 4000, null),
          withTimeout(
            api.listModels(connectionId, false).catch(() => []),
            6000,
            [],
          ),
          withTimeout(api.listComponentGallery().catch(() => []), 4000, []),
        ]);
        if (cancelled) return;
        if (!conn) {
          setError("Could not load connection (timeout or API down). Templates still available.");
        } else {
          setConnection(conn);
        }
        setTemplates(dedupeTemplates(tpls.length ? tpls : FALLBACK_TEMPLATES));
        setComponentGallery(gallery || []);
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
          setTemplates(dedupeTemplates(FALLBACK_TEMPLATES));
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
        multi_company: multiCompany,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setResult(res);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        reportApiError(err, setError, { fallback: "Scaffold failed", toast: true });
      }
    } finally {
      setBusy(false);
    }
  }

  async function onCheckOverlap() {
    if (nlPrompt.trim().length < 3) return;
    setOverlapBusy(true);
    setError(null);
    setOverlapChoice(null);
    setOverlapFindingId(null);
    try {
      const res = await api.checkOverlap({
        prompt: nlPrompt.trim(),
        connection_id: connectionId,
        grain: grainOverride || undefined,
        host_model: connectPoints?.host_model ? String(connectPoints.host_model) : undefined,
      });
      setOverlapFindings(res.findings ?? []);
      if (res.grain_label) setGrainLabel(res.grain_label);
      if (res.grain) {
        setEffectiveGrain(res.grain);
        if (res.grain === "full_app") setConnectPointsApproved(true);
      }
    } catch (err) {
      reportApiError(err, setError, { fallback: "Overlap check failed", toast: true });
    } finally {
      setOverlapBusy(false);
    }
  }

  function onOverlapUse(finding: (typeof overlapFindings)[number]) {
    setOverlapChoice("use");
    setOverlapFindingId(finding.id);
    if (finding.deep_link) {
      window.location.href = finding.deep_link;
    }
  }

  function onOverlapExtend(finding: (typeof overlapFindings)[number]) {
    setOverlapChoice("extend");
    setOverlapFindingId(finding.id);
    setGrainOverride("feature_slice");
    if (finding.extend_host_model) {
      setConnectPoints({
        host_model: finding.extend_host_model,
        form_xpath: "//sheet",
        form_position: "inside",
      });
    }
    void onReviewConnectPoints();
  }

  function onOverlapBuildAnyway(findingId?: string) {
    setOverlapChoice("build_anyway");
    setOverlapFindingId(findingId ?? null);
  }

  async function onReviewConnectPoints() {
    if (nlPrompt.trim().length < 3) return;
    setConnectReviewBusy(true);
    setError(null);
    setConnectPointsApproved(false);
    setAiDraft(null);
    try {
      const res = await api.proposeConnectPoints({
        prompt: nlPrompt.trim(),
        connection_id: connectionId,
        grain: grainOverride || undefined,
        gallery_id: selectedGalleryId || undefined,
        connect_points: connectPoints ?? undefined,
      });
      setEffectiveGrain(res.grain);
      setGrainLabel(res.grain_label);
      if (res.grain === "full_app") setConnectPointsApproved(true);
      setConnectPoints(res.connect_points ?? null);
      setHostCandidates(res.host_candidates ?? []);
      if (res.gallery_id && !selectedGalleryId) {
        setSelectedGalleryId(res.gallery_id);
      }
      if (res.warnings?.length) {
        setAiWarnings(res.warnings);
      }
      if (!res.requires_review) {
        setConnectPointsApproved(true);
      }
    } catch (err) {
      reportApiError(err, setError, {
        fallback: "Connect-points review failed",
        toast: true,
      });
    } finally {
      setConnectReviewBusy(false);
    }
  }

  async function onDraftFromPrompt(opts?: {
    reuseOverride?: string[];
    rejectedOverride?: string[];
  }) {
    if (!canDraftModule) return;
    const effectiveRejected = opts?.rejectedOverride ?? rejectedInferredReuse;
    const effectiveReuse = (opts?.reuseOverride ?? reuseModels).filter(
      (m) => !effectiveRejected.includes(m),
    );
    setAiBusy(true);
    setError(null);
    setAiNote(null);
    setAiWarnings([]);
    setAiRefusals([]);
    setGenUiResult(null);
    try {
      const res = await api.draftModuleFromPrompt(nlPrompt.trim(), {
        connection_id: connectionId,
        reuse_models: effectiveReuse,
        rejected_reuse_models: effectiveRejected,
        grain: grainOverride || undefined,
        gallery_id: selectedGalleryId || undefined,
        host_model: connectPoints?.host_model
          ? String(connectPoints.host_model)
          : undefined,
        connect_points: connectPoints ?? undefined,
        overlap_choice: overlapChoice ?? undefined,
        overlap_finding_id: overlapFindingId ?? undefined,
      });
      setAiDraft(res.draft);
      setAiNote(res.note ?? "Draft only — does not apply.");
      setAiWarnings(res.warnings ?? []);
      setAiRefusals(res.refusals ?? []);
      if (res.grain_label) setGrainLabel(res.grain_label);
      if (res.grain) setEffectiveGrain(res.grain);
      if (res.connect_points) setConnectPoints(res.connect_points);
      if (res.host_candidates?.length) setHostCandidates(res.host_candidates);
    } catch (err) {
      setAiDraft(null);
      reportApiError(err, setError, { fallback: "AI draft failed", toast: true });
      setAiNote(
        "Use Car Rental / Library template below if Ollama is unavailable. " +
          "Domain prompts like “car rental” still work offline via curated packs.",
      );
    } finally {
      setAiBusy(false);
    }
  }

  function draftWithMultiCompany() {
    if (!aiDraft) return null;
    return multiCompany ? { ...aiDraft, multi_company: true } : aiDraft;
  }

  async function onGenerateUiFromDraft(phrase: string, forceSkipValidate = false) {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setBusy(true);
    setError(null);
    setGenUiResult(null);
    try {
      const res = await api.applyModuleSpec(connectionId, {
        spec,
        confirm_advanced: true,
        confirm_phrase: phrase,
        skip_validate_live: forceSkipValidate || skipValidateLive,
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
        reportApiError(err, setError, { fallback: "Generate UI failed", toast: true });
      }
    } finally {
      setBusy(false);
    }
  }

  async function onPrepareGenerateUi() {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setBusy(true);
    setError(null);
    setValidateLiveResult(null);
    setSkipValidateLive(false);
    try {
      const validation = await api.validateModuleSpecLive(connectionId, { spec });
      setValidateLiveResult(validation);
      if (validation.ok) {
        setGenUiConfirmOpen(true);
      } else {
        setError(
          `${validation.message} — fix the draft or confirm override in the dialog.`,
        );
        setGenUiConfirmOpen(true);
        setSkipValidateLive(false);
      }
    } catch (err) {
      reportApiError(err, setError, { fallback: "Validate-live failed", toast: true });
    } finally {
      setBusy(false);
    }
  }


  const inferredReuseSuggestions = useMemo(() => {
    if (!aiDraft) return [];
    const plan = (
      aiDraft.reuse as
        | {
            plan?: {
              decisions?: Array<{
                model?: string;
                reason?: string;
                source?: string;
                confirmed?: boolean;
                link_only?: boolean;
                module?: string;
              }>;
            };
          }
        | undefined
    )?.plan;
    return (plan?.decisions ?? []).filter(
      (d) =>
        d.model &&
        !d.confirmed &&
        !rejectedInferredReuse.includes(String(d.model)) &&
        (d.source === "inferred" || d.source === "pack_reuse_stock"),
    );
  }, [aiDraft, rejectedInferredReuse]);

  const installableReuseSuggestions = useMemo(() => {
    if (!aiDraft) return [];
    const plan = (
      aiDraft.reuse as
        | {
            plan?: {
              decisions?: Array<{
                model?: string;
                reason?: string;
                source?: string;
                confirmed?: boolean;
                link_only?: boolean;
                module?: string;
              }>;
            };
          }
        | undefined
    )?.plan;
    return (plan?.decisions ?? []).filter(
      (d) =>
        d.model &&
        !d.confirmed &&
        !rejectedInferredReuse.includes(String(d.model)) &&
        d.source === "installable",
    );
  }, [aiDraft, rejectedInferredReuse]);

  async function confirmInferredReuse(model: string) {
    const nextReuse = reuseModels.includes(model)
      ? reuseModels
      : [...reuseModels, model];
    setReuseModels(nextReuse);
    await onDraftFromPrompt({ reuseOverride: nextReuse });
  }

  async function rejectInferredReuse(model: string) {
    const nextRejected = rejectedInferredReuse.includes(model)
      ? rejectedInferredReuse
      : [...rejectedInferredReuse, model];
    const nextReuse = reuseModels.filter((m) => m !== model);
    setRejectedInferredReuse(nextRejected);
    setReuseModels(nextReuse);
    await onDraftFromPrompt({
      reuseOverride: nextReuse,
      rejectedOverride: nextRejected,
    });
  }

  async function confirmInstallableReuse(model: string) {
    const nextReuse = reuseModels.includes(model)
      ? reuseModels
      : [...reuseModels, model];
    setReuseModels(nextReuse);
    await onDraftFromPrompt({ reuseOverride: nextReuse });
  }

  async function rejectInstallableReuse(model: string) {
    const nextRejected = rejectedInferredReuse.includes(model)
      ? rejectedInferredReuse
      : [...rejectedInferredReuse, model];
    const nextReuse = reuseModels.filter((m) => m !== model);
    setRejectedInferredReuse(nextRejected);
    setReuseModels(nextReuse);
    await onDraftFromPrompt({
      reuseOverride: nextReuse,
      rejectedOverride: nextRejected,
    });
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
      reportApiError(err, setError, { fallback: "Export failed", toast: true });
    } finally {
      setBusy(false);
    }
  }

  const activeStep = pipelineStepIndex(aiDraft);

  return (
    <div className="mx-auto max-w-4xl" data-testid="draft-studio">
      <PageHeader
        title="Draft Studio"
        description={
          connection
            ? `${connection.name} · describe an app, create a draft, then apply it to Odoo — or pick a template below`
            : connectionId
        }
      />
      <VersionAwarenessBanner capabilities={connection?.capabilities} />

      <ol className="mb-6 flex flex-wrap gap-2 text-xs">
        {PIPELINE_STEPS.map((step, i) => (
          <li
            key={step}
            className={
              i <= activeStep
                ? "rounded-full border border-accent/30 bg-accent-subtle px-2.5 py-1 font-medium text-accent"
                : "rounded-full border border-border-subtle px-2.5 py-1 text-muted"
            }
          >
            {step}
          </li>
        ))}
      </ol>

      <Card className="mb-6 space-y-4 p-5">
        <Input
          label="Display name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="e.g. Acme Library"
        />
        <Input
          label="Technical prefix (optional)"
          value={technicalPrefix}
          onChange={(e) => setTechnicalPrefix(e.target.value)}
          placeholder="e.g. lib_demo → x_lib_demo_book"
          hint="Omit for fixed template model names (library: x_lib_book, …)."
          className="font-mono"
        />
        <label className="flex max-w-md items-start gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={multiCompany}
            onChange={(e) => setMultiCompany(e.target.checked)}
            className="mt-1"
          />
          <span>
            <span className="font-medium">Multi-company aware</span>
            <span className="mt-0.5 block text-xs text-muted">
              Adds company field + record rules for template scaffold, Generate UI, and library export.
            </span>
          </span>
        </label>
      </Card>

        {componentGallery.length > 0 && (
          <Card className="mb-6 p-5">
            <h2 className="text-xl font-semibold text-ink">Component gallery</h2>
            <p className="mt-1 text-xs text-muted">
              Reusable slices that attach to stock or custom hosts.
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {componentGallery.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => {
                    setSelectedGalleryId(c.id);
                    setNlPrompt(`Add ${c.name.toLowerCase()} to my ${c.host_slot.replace(".", " ")}s`);
                    setConnectPointsApproved(false);
                    setConnectPoints(null);
                  }}
                  className={`rounded-md border p-3 text-left text-sm transition ${
                    selectedGalleryId === c.id
                      ? "border-accent bg-accent-subtle"
                      : "border-border-subtle hover:bg-surface-muted"
                  }`}
                >
                  <span className="font-semibold text-ink">{c.name}</span>
                  <span className="mt-1 block text-xs text-muted">{c.description}</span>
                  <span className="mt-1 block font-mono text-[10px] text-accent">
                    Host: {c.host_slot}
                  </span>
                </button>
              ))}
            </div>
          </Card>
        )}

        <Card className="mb-6 p-5">
          <h2 className="text-xl font-semibold text-ink">Describe your app</h2>
          <p className="mt-1 text-sm text-muted">
            AI drafts a reviewable spec ({aiEnabled ? "Ollama on" : "AI off"}
            {ollamaDetail ? ` · ${ollamaDetail}` : ""}). Nothing is written to Odoo until
            you click <strong className="font-medium text-ink">Apply to Odoo</strong>.
          </p>

          <ol className="mt-4 grid gap-2 sm:grid-cols-3" data-testid="draft-studio-steps">
            {[
              {
                n: 1,
                title: "Describe",
                detail: "Write what you need in plain language.",
                done: nlPrompt.trim().length >= 3,
              },
              {
                n: 2,
                title: "Create draft",
                detail: "AI returns JSON you can review and edit.",
                done: Boolean(aiDraft),
              },
              {
                n: 3,
                title: "Apply to Odoo",
                detail: "Creates models, fields, and views on this connection.",
                done: Boolean(genUiResult),
              },
            ].map((step) => (
              <li
                key={step.n}
                className={`rounded-md border px-3 py-2 text-sm ${
                  step.done
                    ? "border-accent/40 bg-accent-subtle"
                    : "border-border-subtle bg-surface-muted"
                }`}
              >
                <p className="font-medium text-ink">
                  {step.n}. {step.title}
                </p>
                <p className="mt-0.5 text-xs text-muted">{step.detail}</p>
              </li>
            ))}
          </ol>
          <Textarea
            className="mt-3"
            value={nlPrompt}
            onChange={(e) => {
              setNlPrompt(e.target.value);
              setConnectPointsApproved(false);
              setConnectPoints(null);
              setOverlapFindings([]);
              setOverlapChoice(null);
              setOverlapFindingId(null);
            }}
            rows={3}
            placeholder="Car rental fleet: vehicles, contracts, deposits, overdue returns…"
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Select
              label="Grain override"
              options={[
                { value: "", label: "Auto-detect" },
                { value: "field_pack", label: "Field pack" },
                { value: "feature_slice", label: "Component / feature slice" },
                { value: "full_app", label: "Full app" },
              ]}
              value={grainOverride}
              onChange={(e) => {
                setGrainOverride(e.target.value);
                setConnectPointsApproved(e.target.value === "full_app");
                setConnectPoints(null);
              }}
            />
            {grainLabel ? <Badge variant="info">Detected: {grainLabel}</Badge> : null}
          </div>

          {overlapFindings.length > 0 ? (
            <section
              className="mt-4 space-y-3 rounded-md border border-border-subtle bg-surface-muted p-4"
              data-testid="overlap-findings"
            >
              <h3 className="text-sm font-semibold text-ink">Already exists on this instance</h3>
              <p className="text-xs text-muted">
                Review before drafting — choose how to proceed for each finding.
              </p>
              <ul className="space-y-3">
                {overlapFindings.map((f) => (
                  <li key={f.id} className="border-b border-border-subtle pb-3 text-sm">
                    <p className="font-medium">{f.title}</p>
                    <p className="mt-1 text-xs text-muted">{f.evidence}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {f.deep_link ? (
                        <Button type="button" size="sm" variant="secondary" onClick={() => onOverlapUse(f)}>
                          Use what exists
                        </Button>
                      ) : null}
                      {f.extend_host_model ? (
                        <Button type="button" size="sm" variant="secondary" onClick={() => onOverlapExtend(f)}>
                          Extend it
                        </Button>
                      ) : null}
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => onOverlapBuildAnyway(f.id)}
                      >
                        Build anyway
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
              {overlapChoice === "build_anyway" ? (
                <Callout variant="warning" title="Building anyway">
                  Your choice is recorded on the draft audit trail.
                </Callout>
              ) : null}
            </section>
          ) : null}

          {connectPoints && needsConnectReview ? (
            <section
              className="mt-4 rounded-md border border-border-subtle bg-surface-muted p-4"
              data-testid="connect-points-review"
            >
              <h3 className="text-sm font-semibold text-ink">Connect points (review before draft)</h3>
              <p className="mt-1 text-xs text-muted">
                Confirm host model and form placement. Edit below, then approve before drafting.
              </p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2 text-xs">
                <label>
                  Host model
                  <input
                    value={String(connectPoints.host_model ?? "")}
                    onChange={(e) => {
                      setConnectPoints({ ...connectPoints, host_model: e.target.value });
                      setConnectPointsApproved(false);
                    }}
                    className="mt-1 w-full rounded border border-border-subtle bg-surface px-2 py-1 font-mono"
                  />
                </label>
                <label>
                  Form xpath
                  <input
                    value={String(connectPoints.form_xpath ?? "//sheet")}
                    onChange={(e) => {
                      setConnectPoints({ ...connectPoints, form_xpath: e.target.value });
                      setConnectPointsApproved(false);
                    }}
                    className="mt-1 w-full rounded border border-border-subtle bg-surface px-2 py-1 font-mono"
                  />
                </label>
              </div>
              {hostCandidates.length > 1 ? (
                <p className="mt-2 text-xs text-muted">
                  Other hosts:{" "}
                  {hostCandidates
                    .slice(1, 4)
                    .map((h) => `${h.label} (${h.model})`)
                    .join(" · ")}
                </p>
              ) : null}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  disabled={connectPointsApproved}
                  onClick={() => setConnectPointsApproved(true)}
                >
                  {connectPointsApproved ? "Approved" : "Approve connect points"}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  loading={connectReviewBusy}
                  onClick={() => void onReviewConnectPoints()}
                >
                  Re-run review
                </Button>
              </div>
            </section>
          ) : null}

          <div className="mt-4">
            <p className="text-xs uppercase tracking-wide text-muted">
              Reuse existing Odoo models
            </p>
            <p className="mt-1 text-xs text-muted">
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
                        ? "border-border-subtle bg-surface-raised text-muted"
                        : "border-border-subtle text-muted hover:border-[#4a3550]"
                    }`}
                  >
                    {on ? "✓ " : ""}
                    {m}
                  </button>
                );
              })}
            </div>
            {availableModels.length > 0 && (
              <label className="mt-3 block text-xs text-muted">
                Or pick from this connection
                <select
                  className="mt-1 w-full max-w-md border border-border-subtle bg-surface px-2 py-1.5 font-mono text-xs text-ink"
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
              <p className="mt-2 font-mono text-xs text-muted">
                Selected: {reuseModels.join(", ")}
              </p>
            )}
            {inferredReuseSuggestions.length > 0 ? (
              <div
                className="mt-3 space-y-2 rounded-md border border-border-subtle bg-surface-muted p-3"
                data-testid="inferred-reuse-suggestions"
              >
                <p className="text-xs font-medium text-ink">Suggested stock models</p>
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
                        onClick={() => void confirmInferredReuse(String(d.model))}
                        data-testid={`confirm-reuse-${d.model}`}
                      >
                        Use installed model
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={aiBusy}
                        onClick={() => void rejectInferredReuse(String(d.model))}
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
                className="mt-3 space-y-2 rounded-md border border-amber-200 bg-amber-50/50 p-3 dark:border-amber-900/40 dark:bg-amber-950/20"
                data-testid="installable-reuse-suggestions"
              >
                <p className="text-xs font-medium text-ink">Installable Odoo apps</p>
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
                        onClick={() => void confirmInstallableReuse(String(d.model))}
                        data-testid={`confirm-install-reuse-${d.model}`}
                      >
                        Install &amp; reuse
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={aiBusy}
                        onClick={() => void rejectInstallableReuse(String(d.model))}
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

          <div className="mt-4 space-y-3 rounded-md border border-border-subtle bg-surface-muted p-4">
            <p className="text-sm font-medium text-ink">What to click</p>
            <div className="flex flex-wrap gap-2">
              {needsConnectReview ? (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={connectReviewBusy || nlPrompt.trim().length < 3}
                  loading={connectReviewBusy}
                  onClick={() => void onReviewConnectPoints()}
                  data-testid="review-connect-points"
                >
                  Review connect points
                </Button>
              ) : null}
              <Button
                type="button"
                variant="primary"
                disabled={aiBusy || !canDraftModule}
                loading={aiBusy}
                title={
                  overlapFindings.length > 0 && !overlapResolved
                    ? "Resolve overlap findings first (Build anyway, Use, or Extend)"
                    : needsConnectReview && !connectPointsApproved
                      ? "Review and approve connect points first"
                      : undefined
                }
                onClick={() => void onDraftFromPrompt()}
                data-testid="create-draft"
              >
                1. Create draft
              </Button>
              <Button
                type="button"
                variant={aiDraft ? "primary" : "secondary"}
                disabled={!aiDraft || busy || !canGenerateUi}
                title={generateUiBlocked ?? undefined}
                onClick={() => void onPrepareGenerateUi()}
                data-testid="apply-to-odoo"
              >
                2. Apply to Odoo
              </Button>
            </div>
            {!aiDraft ? (
              <p className="text-xs text-muted">
                {nlPrompt.trim().length < 3
                  ? "Type your app idea above (at least a few words), then click Create draft."
                  : needsConnectReview && (!connectPoints || !connectPointsApproved)
                    ? "Component / field pack: click Review connect points, approve the host model, then Create draft."
                    : overlapFindings.length > 0 && !overlapResolved
                      ? "Resolve overlap findings above (Use, Extend, or Build anyway), then Create draft."
                      : isFullAppGrain
                        ? "Full app detected — click Create draft. AI generates JSON below; nothing touches Odoo until Apply."
                        : "Click Create draft — AI detects full app vs component and generates JSON for review."}
              </p>
            ) : (
              <p className="text-xs text-muted">
                Draft ready below. Review the JSON, then click{" "}
                <strong className="font-medium text-ink">Apply to Odoo</strong> to generate models
                and views on this connection.
              </p>
            )}
            <div className="flex flex-wrap gap-2 border-t border-border-subtle pt-3">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                loading={overlapBusy}
                disabled={nlPrompt.trim().length < 3}
                onClick={() => void onCheckOverlap()}
                data-testid="check-overlap"
              >
                Check overlap
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={!aiDraft}
                onClick={() => {
                  if (!aiDraft) return;
                  const modelCount = Array.isArray(aiDraft.models)
                    ? aiDraft.models.length
                    : 0;
                  if (modelCount === 0) {
                    setError(
                      "Draft has 0 models — create the draft again before opening the editor.",
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
              >
                Edit draft (advanced)
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setAiDraft(null);
                  setNlPrompt("");
                  setAiWarnings([]);
                  setConnectPoints(null);
                  setConnectPointsApproved(false);
                  setOverlapFindings([]);
                  setOverlapChoice(null);
                  setOverlapFindingId(null);
                  setGenUiResult(null);
                  setValidateLiveResult(null);
                  setGrainLabel(null);
                  setEffectiveGrain("");
                  setAiNote(null);
                }}
              >
                Clear
              </Button>
            </div>
          </div>
          {needsConnectReview && !connectPointsApproved ? (
            <Callout variant="info" title="Component grain" className="mt-3">
              This prompt looks like a feature slice or field pack — review connect points and
              approve before creating the draft.
            </Callout>
          ) : null}
          {aiDraft && generateUiBlocked ? (
            <Callout variant="warning" title="Apply to Odoo blocked" className="mt-3">
              {generateUiBlocked}
            </Callout>
          ) : null}
          {aiNote ? (
            <Callout variant="info" title="Note" className="mt-3">
              {aiNote}
            </Callout>
          ) : null}
          {genUiResult ? (
            <Callout variant="info" title="Applied to Odoo" className="mt-2">
              {genUiResult}
            </Callout>
          ) : null}
          {draftNeedsRegenerate ? (
            <Callout variant="warning" title="Generic placeholders detected" className="mt-2">
              <p className="text-sm">
                The AI model timed out — generic placeholders filled the gaps. Regenerate for
                domain-specific results.
              </p>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="mt-2"
                disabled={aiBusy || !canDraftModule}
                loading={aiBusy}
                onClick={() => void onDraftFromPrompt()}
                data-testid="regenerate-draft"
              >
                Regenerate
              </Button>
            </Callout>
          ) : null}
          {aiWarnings.length > 0 ? (
            <Callout variant="warning" title="Draft warnings" className="mt-2">
              <ul className="list-disc space-y-1 pl-5">
                {aiWarnings.slice(0, 12).map((w, i) => (
                  <li key={`${i}-${w}`}>{w}</li>
                ))}
              </ul>
            </Callout>
          ) : null}
          {connectPoints && !needsConnectReview ? (
            <section className="mt-4 border border-border-subtle bg-surface p-4">
              <h3 className="text-sm font-semibold text-muted">Connect points</h3>
              <p className="mt-1 text-xs text-muted">
                Full-app draft — connect points not required.
              </p>
            </section>
          ) : null}
          {aiRefusals.length > 0 ? (
            <div className="mt-4 space-y-2" data-testid="protected-refusals">
              {aiRefusals.map((r, i) => (
                <Callout key={`${r.protected_module}-${i}`} variant="warning" title="Protected module">
                  <p className="text-sm">
                    <strong>{r.requested_capability}</strong>
                  </p>
                  <p className="mt-1 break-all font-mono text-sm text-muted">
                    Model: {r.protected_module}
                  </p>
                  <p className="mt-1 text-sm">{r.reason || r.requested_capability}</p>
                  <p className="mt-2 text-sm text-accent">{r.safe_alternative}</p>
                </Callout>
              ))}
            </div>
          ) : null}
          {aiDraft && (
            <>
              {Boolean(aiDraft._component) || (aiDraft.grain && aiDraft.grain !== "full_app") ? (
                <p className="mt-3 text-xs text-muted">
                  Component summary — host{" "}
                  <span className="font-mono">
                    {String(
                      (connectPoints?.host_model as string) ||
                        (aiDraft.connect_points as { host_model?: string } | undefined)
                          ?.host_model ||
                        "?",
                    )}
                  </span>
                  · depends {JSON.stringify(aiDraft.depends ?? [])} · no new app root
                </p>
              ) : (
                <p className="mt-3 text-xs text-muted">
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
              )}
              {Array.isArray(aiDraft.models) ? (
                <ul className="mt-3 space-y-1 text-sm" data-testid="draft-model-review">
                  {(aiDraft.models as Array<{ model?: string; description?: string }>).map(
                    (m) => (
                      <li key={String(m.model)} className="flex items-center gap-2">
                        <span className="font-mono text-muted">{m.model}</span>
                        <AskWhyButton
                          subject={String(m.model)}
                          context={`Draft model ${m.model}${m.description ? `: ${m.description}` : ""}`}
                        />
                      </li>
                    ),
                  )}
                </ul>
              ) : null}
              <CodeBlock
                className="mt-2"
                language="json"
                code={JSON.stringify(aiDraft, null, 2)}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <SuggestTemplateButton spec={aiDraft} connectionId={connectionId} />
                {(aiDraft._component ||
                  (typeof aiDraft.grain === "string" &&
                    aiDraft.grain !== "full_app")) && (
                  <SaveAsComponentButton spec={aiDraft} />
                )}
              </div>
            </>
          )}
        </Card>

        {loading ? (
          <div className="mt-4 space-y-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : null}
        {error ? <ErrorNotice message={error} className="mt-4" /> : null}

        <div className="mt-10 border-t border-border-subtle pt-8">
          <h2 className="text-xl font-semibold text-ink">Ready-made templates</h2>
          <p className="mt-1 text-sm text-muted">
            Skip AI — one click scaffolds a full app (Library, CRM Lite, …) directly on this connection.
          </p>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
                className={`rounded-md border p-4 text-left transition ${
                  !canScaffold
                    ? "cursor-not-allowed border-border-subtle bg-surface-muted opacity-50"
                    : active
                      ? "border-accent bg-accent-subtle"
                      : "border-border-subtle bg-surface-raised hover:bg-surface-muted"
                }`}
              >
                <p className="text-lg font-semibold text-ink">{tpl.name}</p>
                <p className="mt-1 font-mono text-xs text-accent">{tpl.id}</p>
                <p className="mt-2 text-sm text-muted">{tpl.description}</p>
                {blocked ? (
                  <p className="mt-2 text-xs text-warning">{blocked}</p>
                ) : null}
              </button>
            );
          })}
        </div>

        {result ? (
          <Card className="mt-8 p-5" data-testid="scaffold-result">
            <h2 className="text-xl font-semibold text-ink">Scaffold result</h2>
            <p className="mt-2 text-sm text-ink">
              {result.ok ? "Complete" : "Partial"} · {result.message}
            </p>
            <p className="mt-1 text-sm text-muted">
              Template <code className="font-mono text-accent">{result.template_id}</code> ·{" "}
              {result.fields_created} fields created
              {typeof result.view_injects === "number"
                ? ` · ${result.view_injects} view inject(s)`
                : ""}
            </p>
            {result.warnings && result.warnings.length > 0 ? (
              <Callout variant="warning" title="Warnings" className="mt-3">
                <ul className="list-disc space-y-1 pl-5">
                  {result.warnings.map((w, i) => (
                    <li key={`${i}-${w}`}>{w}</li>
                  ))}
                </ul>
              </Callout>
            ) : null}

            <ol
              data-testid="scaffold-checklist"
              className="mt-5 space-y-2 text-sm"
            >
              <li className="flex items-start gap-2 border border-[#1e2f29] px-3 py-2">
                <span
                  className={
                    result.models.length > 0 ? "text-muted" : "text-muted"
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
                      ? "text-muted"
                      : "text-muted"
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
                <span className="text-muted" aria-hidden>
                  →
                </span>
                <Link
                  href={
                    result.models[0]
                      ? `/connections/${connectionId}/designer?model=${encodeURIComponent(result.models[0])}`
                      : `/connections/${connectionId}/designer`
                  }
                  className="text-muted hover:underline"
                >
                  Open designer
                </Link>
              </li>
              <li className="flex items-start gap-2 border border-[#1e2f29] px-3 py-2">
                <span className="text-muted" aria-hidden>
                  →
                </span>
                <Link
                  href={`/connections/${connectionId}`}
                  className="text-muted hover:underline"
                >
                  Run sandbox
                </Link>
                <span className="text-muted">(on connection page)</span>
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
                  <span className="font-mono text-muted">{model}</span>
                  <AskWhyButton subject={model} context={`Scaffold created model ${model}`} />
                  <Link
                    href={`/connections/${connectionId}/builder`}
                    className="text-xs text-muted hover:underline"
                  >
                    Builder
                  </Link>
                  <Link
                    href={`/connections/${connectionId}/designer?model=${encodeURIComponent(model)}`}
                    className="text-xs text-muted hover:underline"
                  >
                    Designer
                  </Link>
                </li>
              ))}
              {result.models.length === 0 && (
                <li className="text-muted">No models reported.</li>
              )}
            </ul>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="secondary" asChild>
                <Link href={`/connections/${connectionId}`}>Back to overview</Link>
              </Button>
              <Button variant="primary" asChild>
                <Link href={`/connections/${connectionId}/builder`}>Open builder</Link>
              </Button>
            </div>
          </Card>
        ) : null}

      <ConfirmDialog
        open={confirmOpen}
        title={`Scaffold ${selected?.name ?? "app"}`}
        warning="This creates models, fields, and views on the live Odoo connection."
        risks={[
          "Live metadata writes on this connection",
          "May create multiple x_* models and ACL rows",
          "Existing models with the same name are skipped or extended",
          ...(multiCompany
            ? ["Adds x_company_id + multi-company record rules on workflow models"]
            : []),
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={onConfirmScaffold}
      />
      <ConfirmDialog
        open={genUiConfirmOpen}
        title="Apply draft to Odoo"
        warning="Applies the ModuleSpec draft: models, fields, views, menus, and smart buttons on this live Odoo connection."
        risks={[
          "Creates ir.model / fields / views / menus",
          "May rewrite primary form arches for custom x_* models (statusbars)",
          "Smart buttons use inherit views — stock forms like Contacts stay intact",
          "Automations in the draft are listed only — create them on Automations page",
          "Prefer a sandbox connection before production",
          ...(validateLiveResult && !validateLiveResult.ok
            ? [
                `Validate-live: ${validateLiveResult.fail_count} failure(s) — override only if you accept broken metadata risk`,
              ]
            : []),
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => {
          setGenUiConfirmOpen(false);
          setSkipValidateLive(false);
        }}
        onConfirm={(phrase) => {
          const forceSkip = Boolean(validateLiveResult && !validateLiveResult.ok);
          void onGenerateUiFromDraft(phrase, forceSkip);
        }}
      />
    </div>
  );
}
