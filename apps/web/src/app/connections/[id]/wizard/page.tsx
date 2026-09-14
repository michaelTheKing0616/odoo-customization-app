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
  ExpertDraftReviewResponse,
  JobRow,
  ProtectedModuleRefusal,
  ScaffoldResult,
  ReuseModelRow,
} from "@/lib/api";
import {
  scaffoldApplyAllowed,
  scaffoldApplyBlockedReason,
  scaffoldOptsFromSpec,
} from "@/lib/capabilities";
import { AskWhyButton } from "@/components/expert/AskWhyButton";
import { useShell } from "@/context/ShellContext";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { reportApiError, isApiNotFound } from "@/lib/api-error";
import { Button } from "@/components/ui/Button";
import { InfinityLoop } from "@/components/loading-ui/infinity-loop";
import { Callout } from "@/components/ui/Callout";
import { Card, PageHeader, Skeleton } from "@/components/ui/layout-primitives";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { Badge } from "@/components/ui/Badge";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { DraftOdooPreview } from "@/components/odoo-preview";
import { HostInstallPanel } from "@/components/studio/HostInstallDialog";
import { odooMenuUrl, odooViewUrl } from "@/lib/odoo-urls";
import { JobPollError, pollJob } from "@/lib/jobs";
import {
  draftFromJobResult,
  pickRecoverableDraft,
  resolveJobDraftOutcome,
  successNoteForDraft,
} from "@/lib/draft-job-outcome";
import { confirmedReuseModelsFromDraft } from "@/lib/reuse-chips";
import { SCORE_BARS } from "@/lib/copy-guide";
import {
  briefTextForJobAutopilot,
  stashJobAutopilotBrief,
} from "@/lib/job-brief-handoff";
import { stashPromptForStudio } from "@/lib/studio-session";
import {
  busyLabelFromJobResult,
  draftFinisherComplete,
  generationEngineFromDraft,
  isOptionAAuthoredDraft,
  isRefuseCloneDraft,
  isStockReuseDraft,
  optionAAuthoringPassed,
  optionASettingsFromDraft,
  residualFormPreviewFromDraft,
  stockAppsFromDraft,
  hostInstallOffersFromDraft,
  authoringFindingsWithoutHostInstall,
  type HostInstallOffer,
  wantsModuleDelivery,
} from "@/lib/draft-form-preview";
import { primaryCustomModelFromDraft, viewDesignerHref } from "@/lib/draft-models";
import {
  displayedCertificationTier,
  expertCloserHint,
  expertShouldRepair,
  liveApplyGapBanner,
  unfinishedDraftBanner,
} from "@/lib/draft-studio-banners";
import {
  draftEnrichmentClean,
  withEnrichmentCleanFlags,
} from "@/lib/draft-llm-status";
import {
  operatorSurfaceFromDraft,
  operatorSurfaceHasPlacement,
} from "@/lib/operator-surface";

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

const BACKGROUND_JOB_POLL_MS = 2000;

async function pollBackgroundJob(
  jobId: string,
  opts: {
    setBusyLabel: (label: string | null) => void;
    onPartial?: (partial: Record<string, unknown>) => void;
    maxMs?: number;
  },
): Promise<JobRow> {
  try {
    return await pollJob(jobId, {
      intervalMs: BACKGROUND_JOB_POLL_MS,
      maxAttempts: 2400,
      untilTerminal: true,
      fetchJob: (id) => api.getJob(id),
      onUpdate: (job) => {
        const phase = busyLabelFromJobResult(job.result);
        if (phase) opts.setBusyLabel(phase);
        const partial = draftFromJobResult(job);
        if (partial) opts.onPartial?.(partial);
      },
    });
  } catch (err) {
    if (err instanceof JobPollError && err.job) {
      return err.job;
    }
    throw err;
  }
}

const REUSE_SUGGESTIONS = [
  "res.partner",
  "res.users",
  "product.product",
  "sale.order",
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
      "Fleet, Contacts, contracts, rates, damages & maintenance — invoices stay stock.",
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
  const { openExpert } = useShell();

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
  useSyncShellContext({ draftSummary, route: `/connections/${connectionId}/wizard` });
  const [aiNote, setAiNote] = useState<string | null>(null);
  const [aiWarnings, setAiWarnings] = useState<string[]>([]);
  const draftNeedsRegenerate = Boolean(
    aiDraft &&
      (
        (aiDraft._llm_status as { mode?: string } | undefined)?.mode === "llm_partial" ||
        (aiDraft._llm_status as { mode?: string } | undefined)?.mode === "pack_fallback" ||
        (
          (aiDraft._depth as { seeded?: boolean } | undefined)?.seeded &&
          (aiDraft._llm_status as { mode?: string } | undefined)?.mode === "seed_fallback"
        ) ||
        aiWarnings.some(
          (w) =>
            w.includes("field-deepen skipped") ||
            w.includes("depth met via generic seeds"),
        )
      ),
  );
  const llmStatusMode = (aiDraft?._llm_status as { mode?: string } | undefined)?.mode;
  const scorecard = aiDraft?._scorecard as
    | {
        score_0_10?: number;
        dimensions?: Record<string, number>;
        findings?: Array<{ dimension?: string; element?: string; detail?: string }>;
        validators?: { all_green?: boolean; xml_ok?: boolean; consistency_ok?: boolean };
      }
    | undefined;
  const draftScore = scorecard?.score_0_10;
  const scoreDimensions = scorecard?.dimensions;
  const validatorsGreen = scorecard?.validators?.all_green === true;
  const finisherComplete = draftFinisherComplete(aiDraft);
  const liveApplyBanner = liveApplyGapBanner(aiDraft);
  const liveApply = aiDraft?._live_apply as
    | {
        ready?: boolean;
        findings?: Array<{ detail?: string }>;
        option_a?: string[];
        done_bar?: {
          mode?: string;
          next_step?: string;
          go_live_ready?: boolean;
        };
        go_live_ready?: boolean;
      }
    | undefined;
  const doneBar =
    (aiDraft?._done_bar as
      | { mode?: string; next_step?: string; go_live_ready?: boolean }
      | undefined) ?? liveApply?.done_bar;
  const goLiveReady = Boolean(
    aiDraft?._go_live_ready || liveApply?.go_live_ready || doneBar?.go_live_ready,
  );
  const certification = aiDraft?._certification as
    | {
        tier?: string;
        quality?: number;
        evidence?: number;
        risk?: number;
        hard_failures?: string[];
        option_a_pending?: boolean;
        note?: string;
      }
    | undefined;
  const generationEngine = generationEngineFromDraft(aiDraft);
  const refuseClone = isRefuseCloneDraft(aiDraft);
  const stockReuse = isStockReuseDraft(aiDraft);
  const authoredOptionA = isOptionAAuthoredDraft(aiDraft);
  const authoringPassed = optionAAuthoringPassed(aiDraft);
  const hostInstallOffers = hostInstallOffersFromDraft(aiDraft);
  const leftoverAuthoringFindings = authoringFindingsWithoutHostInstall(aiDraft);
  const zipLocked = authoredOptionA && !authoringPassed;
  const isOdooOnline = connection?.hosting === "online";
  const stockApps = stockAppsFromDraft(aiDraft);
  const operatorSurface = operatorSurfaceFromDraft(aiDraft);
  const jobAutopilotHref = `/connections/${connectionId}/job`;
  const designerHref = viewDesignerHref(connectionId, aiDraft);
  const designerModel = primaryCustomModelFromDraft(aiDraft);
  function stashBriefForJobAutopilot() {
    const text = briefTextForJobAutopilot(aiDraft, nlPrompt);
    if (text) stashJobAutopilotBrief(connectionId, text);
  }
  const certTierDisplay = displayedCertificationTier(aiDraft);
  const certShipReady =
    (certTierDisplay === "Production" || certTierDisplay === "Gold") &&
    !certification?.option_a_pending &&
    !stockReuse;
  const operatorBrief = aiDraft?._operator_brief as
    | {
        formatted?: string;
        capability_path?: string;
        ir_confidence?: string;
        unknowns?: string[];
      }
    | undefined;
  const moduleDelivery = wantsModuleDelivery(aiDraft);
  const residualPreview = residualFormPreviewFromDraft(aiDraft);
  const optionASettings = optionASettingsFromDraft(aiDraft);
  const [zipBusy, setZipBusy] = useState(false);
  const [optionAProveBusy, setOptionAProveBusy] = useState(false);
  const [optionAProveNote, setOptionAProveNote] = useState<string | null>(null);
  const [expertReviewNote, setExpertReviewNote] = useState<string | null>(null);
  const [expertReviewFindings, setExpertReviewFindings] = useState<
    ExpertDraftReviewResponse["findings"]
  >([]);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiBusyLabel, setAiBusyLabel] = useState<string | null>(null);
  const llmStatus = aiDraft?._llm_status as
    | {
        mode?: string;
        reason?: string;
        failed_steps?: string[];
        retry_recommended?: boolean;
        enrichment_clean?: boolean;
      }
    | undefined;
  const llmStatusReason = llmStatus?.reason;
  const showRetryEnrichment = Boolean(
    aiDraft && !aiDraft._component && !stockReuse && !refuseClone,
  );
  // Disabled when enrich finished cleanly (explicit flag or llm_full heuristic).
  const retryEnrichmentDisabled = Boolean(
    aiBusy || !aiDraft || draftEnrichmentClean(aiDraft),
  );
  const llmStatusBanner =
    aiDraft?._component || stockReuse
      ? null
      : llmStatusMode === "llm_partial"
        ? "Some AI steps timed out; the draft was finished from your prompt. Click Retry AI enrichment to wake AI, re-run missed steps, and complete residual fields from your brief if AI stays down."
        : llmStatusMode === "pack_fallback" && llmStatusReason === "residual_recovered"
          ? "Residual completed from your brief (AI was unavailable). Review fields, then Apply — or Retry again when a model is back for LLM polish."
        : llmStatusMode === "pack_fallback" &&
            (llmStatusReason === "timeout" ||
              llmStatusReason === "unavailable" ||
              llmStatusReason === "honesty_seed")
          ? "AI was unavailable on Create draft. Click Retry AI enrichment — it wakes Flash/local/cloud, re-runs missed AI steps, and still completes residual fields from your brief if AI stays down."
        : llmStatusMode === "pack_fallback"
        ? "Draft Studio used the domain pack. Click Retry AI enrichment to tailor when a model is available."
        : llmStatusMode === "seed_fallback" &&
            (aiDraft?._depth as { seeded?: boolean } | undefined)?.seeded
          ? "Depth targets were met via generic operational seeds — review entities before apply."
          : llmStatusMode === "llm_full" && retryEnrichmentDisabled
            ? "AI enrichment completed successfully. Retry stays available only if hygiene gaps return."
          : llmStatusMode === "llm_full"
            ? "AI draft finished. Retry AI enrichment to wake providers and collapse residual hygiene if needed."
          : null;
  const [aiRefusals, setAiRefusals] = useState<ProtectedModuleRefusal[]>([]);
  const unfinishedBanner = unfinishedDraftBanner(aiDraft, { generating: aiBusy });
  const [aiEnabled, setAiEnabled] = useState(false);
  const [aiProviderLabel, setAiProviderLabel] = useState("AI");
  const [ollamaDetail, setOllamaDetail] = useState<string | null>(null);
  const [reuseModels, setReuseModels] = useState<string[]>(["res.partner"]);
  const [rejectedInferredReuse, setRejectedInferredReuse] = useState<string[]>([]);
  const [reuseCatalog, setReuseCatalog] = useState<ReuseModelRow[]>([]);
  const [reuseSearch, setReuseSearch] = useState("");
  const [reuseCatalogStatus, setReuseCatalogStatus] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [reuseCatalogError, setReuseCatalogError] = useState<string | null>(null);
  const [jsonPaste, setJsonPaste] = useState("");
  const [jsonPasteOpen, setJsonPasteOpen] = useState(false);
  const [draftCacheEntries, setDraftCacheEntries] = useState<
    Array<{ id: string; summary: string; prompt: string; updated_at: string | null }>
  >([]);
  const [genUiConfirmOpen, setGenUiConfirmOpen] = useState(false);
  const [eliteBusy, setEliteBusy] = useState(false);
  const [eliteNote, setEliteNote] = useState<string | null>(null);
  const [eliteValidationId, setEliteValidationId] = useState<string | null>(null);
  const [eliteZipBase64, setEliteZipBase64] = useState<string | null>(null);
  const [elitePromoteConfirmOpen, setElitePromoteConfirmOpen] = useState(false);
  const [eliteLintOk, setEliteLintOk] = useState<boolean | null>(null);
  const [eliteLintNote, setEliteLintNote] = useState<string | null>(null);
  const [genUiResult, setGenUiResult] = useState<string | null>(null);
  const [odooAppUrl, setOdooAppUrl] = useState<string | null>(null);
  const [walkthroughConfirmOpen, setWalkthroughConfirmOpen] = useState(false);
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
    if (!stockReuse) return;
    stashBriefForJobAutopilot();
  }, [stockReuse, connectionId, aiDraft, nlPrompt]);

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
        const [conn, tpls, status, gallery] = await Promise.all([
          withTimeout(api.getConnection(connectionId), 8000, null as Connection | null),
          withTimeout(api.listAppTemplates(), 5000, FALLBACK_TEMPLATES),
          withTimeout(api.aiStatus().catch(() => null), 4000, null),
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
        setAiProviderLabel(status?.provider_label || "AI");
        const reachable = status?.provider_reachable ?? status?.ollama_reachable;
        const detail = status?.provider_detail ?? status?.ollama_detail;
        if (reachable === false && detail) {
          setOllamaDetail(detail);
        } else if (reachable === true) {
          setOllamaDetail(null);
        } else if (detail) {
          setOllamaDetail(detail);
        }
        try {
          const cached = await api.listDraftCache(connectionId, 10);
          setDraftCacheEntries(
            (cached || []).map((c) => ({
              id: c.id,
              summary: c.summary,
              prompt: c.prompt,
              updated_at: c.updated_at,
            })),
          );
        } catch {
          setDraftCacheEntries([]);
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

  useEffect(() => {
    let cancelled = false;
    async function loadCatalog() {
      setReuseCatalogStatus("loading");
      setReuseCatalogError(null);
      try {
        const rows = await api.listReuseCatalog(connectionId);
        if (cancelled) return;
        setReuseCatalog(rows);
        setReuseCatalogStatus("ready");
        if (!rows.length) {
          setReuseCatalogError(
            "No stock models returned. Check that this connection’s Odoo is running.",
          );
        }
      } catch (err) {
        if (cancelled) return;
        setReuseCatalogStatus("error");
        setReuseCatalogError(
          err instanceof Error ? err.message : "Failed to load stock Odoo models",
        );
      }
    }
    void loadCatalog();
    return () => {
      cancelled = true;
    };
  }, [connectionId]);

  async function reloadReuseCatalog() {
    setReuseCatalogStatus("loading");
    setReuseCatalogError(null);
    try {
      const rows = await api.listReuseCatalog(connectionId);
      setReuseCatalog(rows);
      setReuseCatalogStatus("ready");
      if (!rows.length) {
        setReuseCatalogError(
          "No stock models returned. Check that this connection’s Odoo is running.",
        );
      }
    } catch (err) {
      setReuseCatalogStatus("error");
      setReuseCatalogError(
        err instanceof Error ? err.message : "Failed to load stock Odoo models",
      );
    }
  }

  // Do NOT sync reuse.plan.models or auto-confirmed connection decisions into chips.
  // Those lists include suggestions. Merging them into operator chips makes the next
  // Confirm/Install reapply treat every sibling as operator_reuse — Suggested and
  // Installable rows vanish. Snapshot restore uses confirmedReuseModelsFromDraft.

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

  async function refreshDraftCacheList() {
    const cached = await api.listDraftCache(connectionId, 10).catch(() => []);
    setDraftCacheEntries(
      (cached || []).map((c) => ({
        id: c.id,
        summary: c.summary,
        prompt: c.prompt,
        updated_at: c.updated_at,
      })),
    );
  }

  async function restoreDraftFromCache(cacheId: string) {
    setAiBusy(true);
    setAiBusyLabel("Restoring cached draft…");
    try {
      const row = await api.getDraftCache(cacheId);
      setAiDraft(row.draft);
      const confirmed = confirmedReuseModelsFromDraft(row.draft);
      if (confirmed.length > 0) {
        setReuseModels(confirmed);
      }
      setNlPrompt(row.prompt || nlPrompt);
      setAiNote(
        expertShouldRepair(row.draft)
          ? `Restored saved snapshot: ${row.summary}. This is not Expert review — click “Ask the Expert to review and fix” only if JSON findings remain.`
          : `Restored saved snapshot: ${row.summary}. No JSON gaps to repair — Expert will leave this spec unchanged.`,
      );
    } catch (err) {
      reportApiError(err, setError, { fallback: "Failed to restore cached draft" });
    } finally {
      setAiBusy(false);
      setAiBusyLabel(null);
    }
  }

  async function proveOptionASandbox() {
    if (!aiDraft) return;
    setOptionAProveBusy(true);
    setOptionAProveNote(null);
    setAiBusy(true);
    setAiBusyLabel("Sandbox install & Option A smoke…");
    try {
      const res = await api.proveOptionA(connectionId, { spec: aiDraft });
      if (res.draft) {
        setAiDraft(res.draft);
      }
      const score =
        typeof res.score_0_10 === "number"
          ? res.score_0_10.toFixed(1)
          : String(
              (res.draft?._scorecard as { score_0_10?: number } | undefined)?.score_0_10 ??
                "—",
            );
      if (res.ok) {
        setOptionAProveNote(
          `Sandbox smoke passed. Score ${score}/10. go_live_ready=${Boolean(res.go_live_ready)} — promote stays human.`,
        );
      } else {
        const msg =
          (res.sandbox as { message?: string } | undefined)?.message ||
          (res.smoke as { message?: string } | undefined)?.message ||
          "Sandbox smoke failed";
        setOptionAProveNote(`${msg} (score capped until smoke passes)`);
      }
    } catch (err) {
      reportApiError(err, setError, { fallback: "Option A sandbox prove failed" });
    } finally {
      setOptionAProveBusy(false);
      setAiBusy(false);
      setAiBusyLabel(null);
    }
  }

  async function askExpertReviewDraft(applyFixes: boolean) {
    if (!aiDraft) return;
    setAiBusy(true);
    setAiBusyLabel(applyFixes ? "Expert review + fixes…" : "Expert review…");
    setExpertReviewNote(null);
    setExpertReviewFindings([]);
    try {
      const res = await api.expertReviewDraft({
        draft: aiDraft,
        user_prompt: nlPrompt.trim(),
        connection_id: connectionId,
        apply_fixes: applyFixes,
      });
      if (res.draft && applyFixes) {
        setAiDraft(res.draft);
      }
      setExpertReviewFindings(res.findings ?? []);
      const after = res.score_after ?? res.score_before;
      setExpertReviewNote(
        `Expert review: ${res.score_before.toFixed(1)}/10 → ${after.toFixed(1)}/10 (${res.verdict})`,
      );
      setAiNote(res.review_markdown);
      if (applyFixes) {
        await refreshDraftCacheList();
      }
    } catch (err) {
      reportApiError(err, setError, { fallback: "Expert draft review failed" });
    } finally {
      setAiBusy(false);
      setAiBusyLabel(null);
    }
  }

  async function retryAiEnrichment() {
    if (!aiDraft || !nlPrompt.trim()) return;
    const status = aiDraft._llm_status as { failed_steps?: string[] } | undefined;
    setAiBusy(true);
    setAiBusyLabel("Retrying AI enrichment (waking providers)…");
    let recoveredPartial: Record<string, unknown> | null = aiDraft;
    try {
      const res = await api.enrichDraft({
        prompt: nlPrompt.trim(),
        draft: aiDraft,
        connection_id: connectionId,
        // Empty = production recovery (deterministic residual + optional LLM polish).
        // Do not force quality/depth/critique — that burned 900s on hollow honesty seeds.
        failed_steps: status?.failed_steps || [],
        async_job: true,
      });
      if (res.job_id) {
        setAiBusyLabel("AI enrichment (background)…");
        const job = await pollBackgroundJob(res.job_id, {
          setBusyLabel: setAiBusyLabel,
          onPartial: (partial) => {
            recoveredPartial = partial;
            setAiDraft(partial);
          },
        });
        const outcome = resolveJobDraftOutcome(
          job,
          "AI enrichment merged into existing draft.",
        );
        if (outcome.kind === "succeeded") {
          const merged = withEnrichmentCleanFlags(outcome.draft);
          setAiDraft(merged);
          setAiWarnings(outcome.warnings ?? []);
          const enrichScore = (merged._scorecard as { score_0_10?: number } | undefined)
            ?.score_0_10;
          const clean = draftEnrichmentClean(merged);
          setAiNote(
            typeof enrichScore === "number"
              ? clean
                ? `AI enrichment complete — draft quality ${enrichScore.toFixed(1)}/10. Retry is disabled until hygiene gaps return.`
                : `AI enrichment complete — draft quality ${enrichScore.toFixed(1)}/10. Retry stays on for remaining hygiene (e.g. create-gated fields).`
              : outcome.note,
          );
        } else if (outcome.kind === "partial") {
          recoveredPartial = outcome.draft;
          setAiDraft(outcome.draft);
          setAiNote(outcome.note);
        } else if (outcome.kind === "still_running") {
          setAiNote(outcome.note);
        } else {
          throw new Error(outcome.error);
        }
      } else {
        const syncDraft = withEnrichmentCleanFlags(res.draft);
        setAiDraft(syncDraft);
        if (res.warnings?.length) setAiWarnings(res.warnings);
        const enrichScore = (syncDraft?._scorecard as { score_0_10?: number } | undefined)
          ?.score_0_10;
        const clean = draftEnrichmentClean(syncDraft);
        setAiNote(
          typeof enrichScore === "number"
            ? clean
              ? `AI enrichment complete — draft quality ${enrichScore.toFixed(1)}/10. Retry is disabled until hygiene gaps return.`
              : `AI enrichment complete — draft quality ${enrichScore.toFixed(1)}/10. Retry stays on for remaining hygiene (e.g. create-gated fields).`
            : "AI enrichment merged into existing draft.",
        );
      }
    } catch (err) {
      const jobErr =
        err instanceof JobPollError
          ? err.job?.error || err.message
          : err instanceof Error
            ? err.message
            : null;
      const listed = await api.listDraftCache(connectionId, 10).catch(() => []);
      const recovered = pickRecoverableDraft(
        recoveredPartial,
        listed || [],
        nlPrompt.trim(),
      );
      if (recovered) {
        setAiDraft(recovered);
        setAiNote(
          (jobErr ? `Enrichment failed: ${jobErr.slice(0, 240)}. ` : "") +
            "Showing last saved snapshot. Restart the API if Retry dies in ~2s " +
            "(code changes need a fresh :8001), then Retry again to wake AI and " +
            "complete residual fields from your brief.",
        );
        if (jobErr) {
          setError(jobErr.slice(0, 400));
        }
        setDraftCacheEntries(
          (listed || []).map((c) => ({
            id: c.id,
            summary: c.summary,
            prompt: c.prompt,
            updated_at: c.updated_at,
          })),
        );
      } else {
        if (!recoveredPartial) setAiDraft(null);
        reportApiError(err, setError, { fallback: "AI enrichment failed" });
      }
    } finally {
      setAiBusy(false);
      setAiBusyLabel(null);
    }
  }

  async function onDraftFromPrompt(opts?: {
    reuseOverride?: string[];
    rejectedOverride?: string[];
    busyLabel?: string;
  }) {
    if (!canDraftModule) return;
    const effectiveRejected = opts?.rejectedOverride ?? rejectedInferredReuse;
    const effectiveReuse = (opts?.reuseOverride ?? reuseModels).filter(
      (m) => !effectiveRejected.includes(m),
    );
    setAiBusy(true);
    setAiBusyLabel(opts?.busyLabel ?? "Creating draft…");
    setError(null);
    setAiNote(null);
    setAiWarnings([]);
    setAiRefusals([]);
    setGenUiResult(null);
    let recoveredPartial: Record<string, unknown> | null = null;
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
        async_job: true,
      });
      if (res.job_id) {
        setAiBusyLabel("Generating draft (background)…");
        const job = await pollBackgroundJob(res.job_id, {
          setBusyLabel: setAiBusyLabel,
          onPartial: (partial) => {
            recoveredPartial = partial;
            setAiDraft(partial);
          },
        });
        const outcome = resolveJobDraftOutcome(job, successNoteForDraft(draftFromJobResult(job)));
        if (outcome.kind === "succeeded") {
          setAiDraft(outcome.draft);
          setAiWarnings(outcome.warnings ?? []);
          setAiNote(outcome.note);
        } else if (outcome.kind === "partial") {
          recoveredPartial = outcome.draft;
          setAiDraft(outcome.draft);
          setAiNote(outcome.note);
        } else if (outcome.kind === "still_running") {
          setAiNote(outcome.note);
        } else {
          throw new Error(outcome.error);
        }
      } else {
        setAiDraft(res.draft);
        setAiNote(res.note ?? "Draft only — does not apply.");
        setAiWarnings(res.warnings ?? []);
        setAiRefusals(res.refusals ?? []);
        if (res.grain_label) setGrainLabel(res.grain_label);
        if (res.grain) setEffectiveGrain(res.grain);
        if (res.connect_points) setConnectPoints(res.connect_points);
        if (res.host_candidates?.length) setHostCandidates(res.host_candidates);
      }
      const cached = await api.listDraftCache(connectionId, 10).catch(() => []);
      setDraftCacheEntries(
        (cached || []).map((c) => ({
          id: c.id,
          summary: c.summary,
          prompt: c.prompt,
          updated_at: c.updated_at,
        })),
      );
    } catch (err) {
      const listed = await api.listDraftCache(connectionId, 10).catch(() => []);
      const recovered = pickRecoverableDraft(
        recoveredPartial,
        listed || [],
        nlPrompt.trim(),
      );
      if (recovered) {
        setAiDraft(recovered);
        setAiNote(
          "Draft recovered from a saved snapshot after the job timed out. " +
            "The JSON below is the last saved pack — not an empty failure. " +
            "Retry AI enrichment to wake AI, re-run missed steps, and complete residual " +
            "fields from your brief if AI stays down.",
        );
        setDraftCacheEntries(
          (listed || []).map((c) => ({
            id: c.id,
            summary: c.summary,
            prompt: c.prompt,
            updated_at: c.updated_at,
          })),
        );
      } else {
        setAiDraft(null);
        reportApiError(err, setError, { fallback: "AI draft failed", toast: true });
        setAiNote(
          "Use Car Rental / Library template below if Ollama is unavailable. " +
            "Domain prompts like “car rental” still work offline via curated packs.",
        );
      }
    } finally {
      setAiBusy(false);
      setAiBusyLabel(null);
    }
  }

  async function reapplyReuseToDraft(
    nextReuse: string[],
    rejected: string[] = rejectedInferredReuse,
  ) {
    if (!aiDraft || !nlPrompt.trim()) return;
    setAiBusy(true);
    setAiBusyLabel("Applying reuse plan…");
    setError(null);
    try {
      const res = await api.reapplyReusePlan({
        prompt: nlPrompt.trim(),
        draft: aiDraft,
        connection_id: connectionId,
        reuse_models: nextReuse,
        rejected_reuse_models: rejected,
      });
      setAiDraft(res.draft);
      if (res.warnings?.length) {
        setAiWarnings((prev) => Array.from(new Set([...prev, ...res.warnings!])));
      }
      const reuseScore = (
        res.draft?._scorecard as { score_0_10?: number } | undefined
      )?.score_0_10;
      setAiNote(
        typeof reuseScore === "number"
          ? `Reuse plan updated — draft quality ${reuseScore.toFixed(1)}/10 (apply-readiness applied).`
          : "Reuse plan updated — apply-readiness passes applied.",
      );
    } catch (err) {
      reportApiError(err, setError, { fallback: "Reuse apply failed", toast: true });
    } finally {
      setAiBusy(false);
      setAiBusyLabel(null);
    }
  }

  function draftWithMultiCompany() {
    if (!aiDraft) return null;
    return multiCompany ? { ...aiDraft, multi_company: true } : aiDraft;
  }

  function downloadEliteZipBase64(tech: string, zipBase64: string) {
    const bin = atob(zipBase64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const blob = new Blob([bytes], { type: "application/zip" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${tech}.zip`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function onDownloadModuleZip() {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setZipBusy(true);
    setError(null);
    try {
      const res = await api.exportModuleSpecZip(connectionId, { spec });
      if (!res.zip_base64) {
        setError("Zip export returned no file.");
        return;
      }
      downloadEliteZipBase64(
        String(spec.technical_name || res.module || "custom_module"),
        res.zip_base64,
      );
      setAiNote(
        "Module zip downloaded. Sandbox-prove before promote — promote stays human.",
      );
    } catch (err) {
      reportApiError(err, setError, { fallback: "Zip export failed", toast: true });
    } finally {
      setZipBusy(false);
    }
  }

  async function refreshEliteLint() {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setEliteLintNote(null);
    try {
      const lint = await api.lintModuleSpecBlocks(connectionId, spec);
      const failing = (lint.blocks ?? []).filter((b) => (b.issues?.length ?? 0) > 0);
      setEliteLintOk(lint.ok && failing.length === 0);
      setEliteLintNote(
        failing.length
          ? `${failing.length} Python block(s) need fixes before promote.`
          : "Custom Python blocks lint clean.",
      );
    } catch (err) {
      setEliteLintOk(null);
      setEliteLintNote(err instanceof Error ? err.message : "Lint check failed");
    }
  }

  async function onEliteValidateModule() {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setEliteBusy(true);
    setEliteNote(null);
    setError(null);
    setEliteValidationId(null);
    setEliteZipBase64(null);
    setEliteLintOk(null);
    setEliteLintNote(null);
    try {
      const lint = await api.lintModuleSpecBlocks(connectionId, spec);
      const failing = (lint.blocks ?? []).filter((b) => (b.issues?.length ?? 0) > 0);
      setEliteLintOk(lint.ok && failing.length === 0);
      if (failing.length) {
        setEliteLintNote(
          `Lint: ${failing.length} block(s) with issues — fix or regenerate before sandbox.`,
        );
      }
      const gate = await api.eliteModuleGate(connectionId, spec);
      if (!gate.gate_passed) {
        setEliteNote(
          `Elite gate: ${(gate.gate_reasons || []).join("; ") || "scorecard below 9.0"}`,
        );
        if (gate.dimensions) {
          const dimLine = Object.entries(gate.dimensions)
            .map(([k, v]) => `${k} ${Number(v).toFixed(1)}`)
            .join(" · ");
          setEliteNote((prev) => `${prev ?? ""}${dimLine ? ` (${dimLine})` : ""}`);
        }
        return;
      }
      const res = await api.eliteModuleAutopilot(connectionId, { spec });
      if (!res.ok) {
        setEliteNote(res.message || "Sandbox validation failed.");
        return;
      }
      setEliteValidationId(res.validation_id ?? null);
      setEliteZipBase64(res.zip_base64 ?? null);
      setEliteNote(
        `Module validated in sandbox (score ${typeof res.score_0_10 === "number" ? res.score_0_10.toFixed(1) : "—"}/10). Ready to promote.`,
      );
    } catch (err) {
      reportApiError(err, setError, { fallback: "Elite validate failed", toast: true });
    } finally {
      setEliteBusy(false);
    }
  }

  async function onElitePromoteModule(phrase: string) {
    const spec = draftWithMultiCompany();
    if (!spec || !eliteValidationId || !eliteZipBase64) return;
    setEliteBusy(true);
    setError(null);
    try {
      const tech = String(spec.technical_name || "custom_module");
      const res = await api.promoteModule(connectionId, {
        technical_name: tech,
        display_name: String(spec.display_name || tech),
        zip_base64: eliteZipBase64,
        validation_id: eliteValidationId,
        install_mode: "python",
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setElitePromoteConfirmOpen(false);
      setEliteNote(res.message || `Promoted ${tech} to this connection.`);
    } catch (err) {
      reportApiError(err, setError, { fallback: "Promote failed", toast: true });
    } finally {
      setEliteBusy(false);
    }
  }

  async function onGenerateUiFromDraft(phrase: string, forceSkipValidate = false) {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setBusy(true);
    setError(null);
    setGenUiResult(null);
    setOdooAppUrl(null);
    try {
      const res = await api.applyModuleSpec(connectionId, {
        spec,
        confirm_advanced: true,
        confirm_phrase: phrase,
        skip_validate_live: forceSkipValidate || skipValidateLive,
      });
      setGenUiConfirmOpen(false);
      setGenUiResult(res.message);
      const menuId = res.root_menu_id;
      const appUrl =
        menuId && connection?.url
          ? odooMenuUrl(connection.url, menuId, res.open_action_id)
          : connection?.url
            ? `${connection.url.replace(/\/$/, "")}/web`
            : null;
      setOdooAppUrl(appUrl);
      const sb = Number(res.smart_buttons || 0);
      const hostHint =
        sb > 0
          ? " Check linked apps’ smart-button row (e.g. Contacts) — see «Where this app shows up»."
          : "";
      setAiNote(
        appUrl
          ? `${res.message} · ${sb} smart button(s). Open the app in Odoo to walk Operations → Inventory → People — you do not pick models one by one.${hostHint}`
          : `${res.message} · ${sb} smart button(s). Open Odoo’s app switcher and click this app.${hostHint}`,
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

  async function onSeedWalkthrough(phrase: string) {
    const spec = draftWithMultiCompany();
    if (!spec) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.seedModuleSpecWalkthrough(connectionId, {
        spec,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setWalkthroughConfirmOpen(false);
      setAiNote(res.message);
      if (res.warnings?.length) setAiWarnings(res.warnings);
      if (res.open_model && res.open_record_id && connection?.url) {
        setOdooAppUrl(
          odooViewUrl(connection.url, res.open_model, "form", null, res.open_record_id),
        );
      }
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        reportApiError(err, setError, { fallback: "Walkthrough seed failed", toast: true });
      }
    } finally {
      setBusy(false);
    }
  }

  function openModuleSpecEditor() {
    if (!aiDraft) return;
    const modelCount = Array.isArray(aiDraft.models) ? aiDraft.models.length : 0;
    if (modelCount === 0) {
      setError("Draft has 0 models — create the draft again before opening ModuleSpec.");
      return;
    }
    try {
      sessionStorage.setItem(`modulespec-draft:${connectionId}`, JSON.stringify(aiDraft));
    } catch {
      setError("Could not store draft in this browser session.");
      return;
    }
    window.location.href = `/connections/${connectionId}/modulespec`;
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

  const autoWiredReuse = useMemo(() => {
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
              }>;
            };
          }
        | undefined
    )?.plan;
    return (plan?.decisions ?? []).filter(
      (d) =>
        d.model &&
        d.confirmed &&
        d.link_only &&
        (d.source === "apply_readiness" ||
          d.source === "pack_reuse_stock" ||
          d.source === "inferred"),
    );
  }, [aiDraft]);

  async function onLoadPastedJson(source: "paste" | "file", file?: File) {
    setError(null);
    setAiNote(null);
    let raw = jsonPaste.trim();
    if (source === "file" && file) {
      raw = await file.text();
    }
    if (!raw) {
      setError("Paste ModuleSpec JSON or choose a .json file.");
      return;
    }
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      setError("Invalid JSON — expected a ModuleSpec object with a models array.");
      return;
    }
    if (!Array.isArray(parsed.models) || parsed.models.length === 0) {
      setError("JSON must include a non-empty models array.");
      return;
    }
    setBusy(true);
    setAiBusyLabel("Preparing JSON draft…");
    try {
      const res = await api.importModuleSpecJson({
        spec: parsed,
        prepare: true,
      });
      setAiDraft(res.spec);
      setAiWarnings(res.warnings ?? []);
      setAiNote(
        res.note ??
          "JSON loaded — review below, then Apply to Odoo (live prep + reuse wiring applied).",
      );
      setGenUiResult(null);
      setValidateLiveResult(null);
      setJsonPasteOpen(false);
    } catch (err) {
      reportApiError(err, setError, { fallback: "JSON import failed", toast: true });
    } finally {
      setBusy(false);
      setAiBusyLabel(null);
    }
  }

  async function confirmInferredReuse(model: string) {
    const nextReuse = reuseModels.includes(model)
      ? reuseModels
      : [...reuseModels, model];
    setReuseModels(nextReuse);
    await reapplyReuseToDraft(nextReuse);
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
      busyLabel:
        "Regenerating with custom models — local Ollama may take several minutes…",
    });
  }

  async function confirmInstallableReuse(model: string) {
    if (!aiDraft || !nlPrompt.trim()) return;
    const plan = (
      aiDraft.reuse as
        | {
            plan?: {
              decisions?: Array<{ model?: string; module?: string }>;
            };
          }
        | undefined
    )?.plan;
    const row = (plan?.decisions ?? []).find((d) => d.model === model);
    const moduleName = row?.module;
    const nextReuse = reuseModels.includes(model)
      ? reuseModels
      : [...reuseModels, model];
    setReuseModels(nextReuse);
    setAiBusy(true);
    setAiBusyLabel(
      moduleName
        ? `Installing ${moduleName} on this connection…`
        : "Applying reuse plan…",
    );
    setError(null);
    try {
      if (moduleName) {
        const installed = await api.installCommunityModule(connectionId, moduleName);
        if (!installed.ok) {
          setError(installed.message || `Failed to install ${moduleName}`);
          return;
        }
        setAiBusyLabel("Applying reuse plan…");
        void reloadReuseCatalog();
      }
      const res = await api.reapplyReusePlan({
        prompt: nlPrompt.trim(),
        draft: aiDraft,
        connection_id: connectionId,
        reuse_models: nextReuse,
        rejected_reuse_models: rejectedInferredReuse,
      });
      setAiDraft(res.draft);
      if (res.warnings?.length) {
        setAiWarnings((prev) => Array.from(new Set([...prev, ...res.warnings!])));
      }
      setAiNote(
        moduleName
          ? `Installed ${moduleName} and reused ${model}. Other installable apps remain below — Install each you need.`
          : `Reuse plan updated for ${model}. Other suggestions remain available.`,
      );
    } catch (err) {
      reportApiError(err, setError, {
        fallback: "Install & reuse failed",
        toast: true,
      });
    } finally {
      setAiBusy(false);
      setAiBusyLabel(null);
    }
  }

  async function installAuthoredHostModule(offer: HostInstallOffer, phrase: string) {
    if (!aiDraft || !offer.module || phrase !== CONFIRM_PHRASE) return;
    setAiBusy(true);
    setAiBusyLabel(`Installing ${offer.label} on this connection…`);
    setError(null);
    let sent = false;
    try {
      const installed = await api.installCommunityModule(connectionId, offer.module);
      if (!installed.ok) {
        setError(installed.message || `Could not install ${offer.label}`);
        return;
      }
      sent = true;
      setAiBusyLabel("Re-checking the authoring gate…");
      const verified = await api.reverifyOptionAAuthoring({
        connection_id: connectionId,
        draft: aiDraft,
      });
      if (verified.draft) setAiDraft(verified.draft);
      setAiNote(
        verified.ok
          ? `${offer.label} is on this connection. Authoring gate passed — zip and sandbox unlocked. Promote stays human.`
          : verified.message ||
            `${offer.label} is installed. The authoring gate still has findings.`,
      );
    } catch (err) {
      if (sent && isApiNotFound(err)) {
        setAiNote(
          `${offer.label} was sent to this Odoo. Authoring re-check returned 404 — kill/restart uvicorn on :8001 without --reload, then refresh and re-check the gate. Do not Live Install the zip.`,
        );
        return;
      }
      reportApiError(err, setError, {
        fallback: `Could not install ${offer.label} on this connection`,
        toast: true,
      });
    } finally {
      setAiBusy(false);
      setAiBusyLabel(null);
    }
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
      busyLabel:
        "Regenerating with custom models — local Ollama may take several minutes…",
    });
  }

  function toggleReuse(model: string) {
    setReuseModels((prev) =>
      prev.includes(model) ? prev.filter((m) => m !== model) : [...prev, model],
    );
  }

  const reuseCatalogByModel = useMemo(() => {
    const map = new Map<string, ReuseModelRow>();
    for (const row of reuseCatalog) {
      map.set(row.model, row);
    }
    return map;
  }, [reuseCatalog]);

  const filteredReuseCatalog = useMemo(() => {
    const needle = reuseSearch.trim().toLowerCase();
    const rows = needle
      ? reuseCatalog.filter((row) => {
          const hay = `${row.model} ${row.name} ${row.app}`.toLowerCase();
          return hay.includes(needle);
        })
      : reuseCatalog;
    return rows.slice(0, 120);
  }, [reuseCatalog, reuseSearch]);

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
            ? `${connection.name} · describe a field, a feature, or a full app — then apply it to Odoo`
            : connectionId
        }
      />
      <VersionAwarenessBanner capabilities={connection?.capabilities} />

      <ol className="mb-6 flex flex-wrap gap-2 text-xs">
        {(aiDraft && (aiDraft._component || aiDraft.grain === "feature_slice" || aiDraft.grain === "field_pack")
          ? (["Host", "Fields", "View", "Ready"] as const)
          : PIPELINE_STEPS
        ).map((step, i) => (
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
          <h2 className="text-xl font-semibold text-ink">What should we implement?</h2>
          <p className="mt-1 text-sm text-muted">
            Same bar as a senior Odoo team: a field pack on a stock form, a feature under an
            existing app, or a full residual workspace. AI drafts a{" "}
            <strong className="font-medium text-ink">ModuleSpec</strong> (
            {aiEnabled ? `${aiProviderLabel} on` : "AI off"}
            {ollamaDetail ? ` · ${ollamaDetail}` : ""}
            ). Nothing is written to Odoo until you click{" "}
            <strong className="font-medium text-ink">Apply to Odoo</strong>.
          </p>

          <ol className="mt-4 grid gap-2 sm:grid-cols-3" data-testid="draft-studio-steps">
            {[
              {
                n: 1,
                title: "Describe",
                detail: "A field on invoices, a feature under Sales, or a full practice app.",
                done: nlPrompt.trim().length >= 3,
              },
              {
                n: 2,
                title: "Draft ModuleSpec",
                detail: "JSON blueprint of models, views, menus, and workflows.",
                done: Boolean(aiDraft),
              },
              {
                n: 3,
                title: "Generate UI",
                detail: "Apply writes the app menu tree. Then Open app in Odoo — no model picker.",
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
            data-testid="draft-nl-prompt"
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
            placeholder="Add SLA due date on invoices — or a law-firm practice with matters, time, and stock quotations…"
          />
          {operatorBrief?.ir_confidence === "low" ||
          generationEngine?.needs_clarification?.question ? (
            <Callout
              variant="warning"
              title="Intent needs confirmation"
              className="mt-3"
              testId="wizard-studio-bridge"
            >
              <p className="text-sm">
                App Studio can ask one clarifying question before generation so the wrong
                vertical pack is not merged silently.
              </p>
              <Link
                href={`/connections/${connectionId}/studio`}
                className="mt-2 inline-flex text-sm font-medium text-accent underline"
                onClick={() => {
                  if (nlPrompt.trim()) stashPromptForStudio(connectionId, nlPrompt.trim());
                }}
              >
                Open in App Studio
              </Link>
            </Callout>
          ) : null}

          <div className="mt-4 rounded-md border border-border-subtle bg-surface-muted p-3">
            <button
              type="button"
              className="flex w-full items-center justify-between text-left text-sm font-medium text-ink"
              onClick={() => setJsonPasteOpen((v) => !v)}
              data-testid="toggle-json-import"
            >
              <span>Or paste ModuleSpec JSON</span>
              <span className="text-xs text-muted">{jsonPasteOpen ? "Hide" : "Show"}</span>
            </button>
            {jsonPasteOpen ? (
              <div className="mt-3 space-y-2">
                <p className="text-xs text-muted">
                  Bring your own draft JSON — we run apply-readiness (reuse wiring, live
                  field naming, promo math) and load it here. Then click Apply to Odoo.
                </p>
                <Textarea
                  value={jsonPaste}
                  onChange={(e) => setJsonPaste(e.target.value)}
                  rows={6}
                  className="font-mono text-xs"
                  placeholder='{"technical_name":"my_app","models":[...]}'
                  data-testid="json-paste-input"
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    loading={busy && aiBusyLabel === "Preparing JSON draft…"}
                    disabled={busy}
                    onClick={() => void onLoadPastedJson("paste")}
                    data-testid="load-json-draft"
                  >
                    Load JSON draft
                  </Button>
                  <label className="inline-flex cursor-pointer items-center">
                    <input
                      type="file"
                      accept=".json,application/json"
                      className="sr-only"
                      data-testid="json-file-input"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) void onLoadPastedJson("file", file);
                        e.target.value = "";
                      }}
                    />
                    <span className="inline-flex h-8 items-center rounded-md border border-border-subtle px-3 text-xs text-ink hover:bg-surface-raised">
                      Upload .json file
                    </span>
                  </label>
                </div>
              </div>
            ) : null}
          </div>

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

          <div className="mt-4" data-testid="stock-model-picker">
            <p className="text-xs uppercase tracking-wide text-muted">
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
                    onClick={() => toggleReuse(m)}
                    className={`border px-2 py-1 font-mono text-xs ${
                      on
                        ? "border-border-subtle bg-surface-raised text-muted"
                        : "border-border-subtle text-muted hover:border-[#4a3550]"
                    }`}
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
                onChange={(e) => setReuseSearch(e.target.value)}
                className="max-w-md font-mono text-xs"
                disabled={reuseCatalogStatus === "loading" && reuseCatalog.length === 0}
              />
              <div className="max-h-48 overflow-y-auto border border-border-subtle bg-surface">
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
                        onClick={() => toggleReuse(row.model)}
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
                    onClick={() => void reloadReuseCatalog()}
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
            {reuseModels.length > 0 && (
              <p className="mt-2 font-mono text-xs text-muted">
                Selected: {reuseModels.join(", ")}
              </p>
            )}
            {autoWiredReuse.length > 0 ? (
              <div
                className="mt-3 space-y-2 rounded-md border border-emerald-900/30 bg-emerald-950/20 p-3"
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
              {aiBusy ? (
                <div
                  className="flex w-full flex-col items-center gap-2 rounded-md border border-border-subtle bg-surface px-4 py-6"
                  data-testid="draft-studio-progress"
                >
                  <InfinityLoop aria-hidden />
                  <p className="text-sm font-medium text-ink" data-testid="generation-phase">
                    {aiBusyLabel || "Creating draft…"}
                  </p>
                </div>
              ) : null}
              <Button
                type="button"
                variant={
                  aiDraft && !moduleDelivery && !refuseClone && !stockReuse
                    ? "primary"
                    : "secondary"
                }
                disabled={
                  !aiDraft ||
                  busy ||
                  !canGenerateUi ||
                  !finisherComplete ||
                  refuseClone ||
                  stockReuse
                }
                title={
                  stockReuse
                    ? "No custom ModuleSpec to apply — use Job Autopilot"
                    : !finisherComplete
                    ? "Wait for the Apps-store finisher (quality score) before applying"
                    : (generateUiBlocked ?? undefined)
                }
                onClick={() => void onPrepareGenerateUi()}
                data-testid="apply-to-odoo"
              >
                2. Apply to Odoo
              </Button>
              {stockReuse ? (
                <Link
                  href={jobAutopilotHref}
                  className="inline-flex items-center justify-center rounded-md bg-ink px-3 py-2 text-sm font-medium text-white"
                  data-testid="open-job-autopilot"
                  onClick={() => stashBriefForJobAutopilot()}
                >
                  Open Job Autopilot
                </Link>
              ) : null}
              {aiDraft && !refuseClone && !stockReuse ? (
                <Button
                  type="button"
                  variant={moduleDelivery ? "primary" : "secondary"}
                  disabled={zipBusy || !finisherComplete || zipLocked}
                  loading={zipBusy}
                  data-testid="download-module-zip"
                  title={
                    zipLocked
                      ? "Authoring gate has not passed — zip stays locked"
                      : undefined
                  }
                  onClick={() => void onDownloadModuleZip()}
                >
                  {moduleDelivery ? "Download module zip" : "Download zip"}
                </Button>
              ) : null}
              <Button
                type="button"
                variant="secondary"
                disabled={!aiDraft || stockReuse}
                data-testid="open-modulespec"
                onClick={() => openModuleSpecEditor()}
              >
                Open ModuleSpec
              </Button>
              {aiDraft && !refuseClone && !stockReuse ? (
                <Button variant="secondary" asChild>
                  <Link
                    href={designerHref}
                    data-testid="open-view-designer"
                    title={
                      designerModel
                        ? `Opens View Designer on ${designerModel}. Apply to Odoo first so the form exists on this connection.`
                        : "Opens View Designer. Apply to Odoo first so views exist on this connection."
                    }
                  >
                    Open View Designer
                  </Link>
                </Button>
              ) : null}
            </div>
            {!aiDraft ? (
              <p className="text-xs text-muted">
                {nlPrompt.trim().length < 3
                  ? "Type what you need (a field, a feature, or a full app), then click Create draft."
                  : needsConnectReview && (!connectPoints || !connectPointsApproved)
                    ? "Component / field pack: click Review connect points, approve the host model, then Create draft."
                    : overlapFindings.length > 0 && !overlapResolved
                      ? "Resolve overlap findings above (Use, Extend, or Build anyway), then Create draft."
                      : isFullAppGrain
                        ? "Full app detected — click Create draft. Stock first; custom models only for the residual. Nothing touches Odoo until Apply."
                        : "Click Create draft — we implement on the host app (inherit + fields + view), not a second ERP."}
              </p>
            ) : (
              <p className="text-xs text-muted">
                The JSON below <strong className="font-medium text-ink">is</strong> the
                ModuleSpec. Click{" "}
                <strong className="font-medium text-ink">Apply to Odoo</strong> to write
                models, forms, and the Operations / Inventory / People menu tree, then{" "}
                <strong className="font-medium text-ink">Open app in Odoo</strong>. Line
                items stay on parent forms — you do not pick models one by one. Or{" "}
                <strong className="font-medium text-ink">Open ModuleSpec</strong> /{" "}
                <strong className="font-medium text-ink">Open View Designer</strong> to
                edit the spec or the live form.
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
                  setOdooAppUrl(null);
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
          {liveApplyBanner ? (
            <Callout
              variant="warning"
              title={liveApplyBanner.title}
              className="mt-3"
              testId={liveApplyBanner.testId}
            >
              {liveApplyBanner.body}
            </Callout>
          ) : null}
          {unfinishedBanner ? (
            <Callout
              variant="warning"
              title={unfinishedBanner.title}
              className="mt-3"
              testId={unfinishedBanner.testId}
            >
              {unfinishedBanner.body}
            </Callout>
          ) : null}
          {aiNote ? (
            <Callout variant="info" title="Note" className="mt-3">
              {aiNote}
            </Callout>
          ) : null}
          {genUiResult ? (
            <Callout variant="info" title="Applied to Odoo" className="mt-2">
              <p>{genUiResult}</p>
              {odooAppUrl ? (
                <p className="mt-2 flex flex-wrap items-center gap-2">
                  <Button asChild variant="primary" size="sm">
                    <a
                      href={odooAppUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      data-testid="open-app-in-odoo"
                    >
                      Open app in Odoo
                    </a>
                  </Button>
                  <span className="text-xs text-muted">
                    Opens the app root. Use Operations, Inventory, and People — not a
                    per-model list.
                  </span>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    data-testid="load-demo-walkthrough"
                    onClick={() => setWalkthroughConfirmOpen(true)}
                  >
                    Load demo walkthrough
                  </Button>
                </p>
              ) : null}
            </Callout>
          ) : null}
          {draftCacheEntries.length > 0 ? (
            <div className="mt-3">
              <p className="text-xs uppercase tracking-wide text-muted">Saved snapshots</p>
              <p className="text-[11px] text-muted">
                Clicking a row replaces the current JSON. It does not run Expert review.
              </p>
              <ul className="mt-1 space-y-1">
                {draftCacheEntries.slice(0, 5).map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      className="text-left text-xs text-muted hover:text-ink underline"
                      onClick={() => void restoreDraftFromCache(c.id)}
                    >
                      {c.summary}
                      {c.updated_at ? ` · ${new Date(c.updated_at).toLocaleString()}` : ""}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {llmStatusBanner || showRetryEnrichment ? (
            <Callout
              variant={
                llmStatusMode === "llm_full" && retryEnrichmentDisabled
                  ? "info"
                  : llmStatusBanner
                    ? "warning"
                    : "info"
              }
              title="AI draft status"
              className="mt-2"
              testId="retry-ai-enrichment"
            >
              <p className="text-sm">
                {llmStatusBanner ||
                  "Retry AI enrichment wakes Flash/local/cloud, re-runs missed polish, and completes residual hygiene from your brief."}
              </p>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="mt-2"
                disabled={retryEnrichmentDisabled}
                loading={aiBusy}
                title={
                  retryEnrichmentDisabled && !aiBusy
                    ? "Enrichment already completed successfully"
                    : "Wake AI providers and re-run missed polish / residual hygiene"
                }
                onClick={() => void retryAiEnrichment()}
                data-testid="retry-ai-enrichment-btn"
              >
                Retry AI enrichment
              </Button>
            </Callout>
          ) : null}
          {operatorBrief?.formatted ? (
            <Callout
              variant="info"
              title={`Structured brief${
                operatorBrief.capability_path
                  ? ` · ${operatorBrief.capability_path}`
                  : ""
              }`}
              className="mt-2"
              testId="operator-brief"
            >
              <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-ink">
                {operatorBrief.formatted}
              </pre>
              {operatorBrief.unknowns?.length ? (
                <p className="mt-2 text-xs text-muted">
                  Unknowns (not assumed): {operatorBrief.unknowns.join("; ")}
                </p>
              ) : null}
            </Callout>
          ) : null}
          {refuseClone ? (
            <Callout
              variant="warning"
              title="Not generated — Apps Store clone refused"
              className="mt-2"
              testId="generation-refuse-clone"
            >
              <p className="text-sm">
                {generationEngine?.honesty ||
                  "This platform does not clone Apps Store or GM modules. Describe the residual process, or ask for the honest POS receipt options template."}
              </p>
            </Callout>
          ) : null}
          {!refuseClone && generationEngine?.honesty ? (
            <Callout
              variant="info"
              title="Honest capability"
              className="mt-2"
              testId="generation-honesty"
            >
              <p className="text-sm">{generationEngine.honesty}</p>
            </Callout>
          ) : null}
          {operatorSurfaceHasPlacement(operatorSurface) && operatorSurface ? (
            <Callout
              variant="info"
              title="Where this app shows up"
              className="mt-2"
              testId="operator-surface"
            >
              {operatorSurface.summary ? (
                <p className="text-sm">{operatorSurface.summary}</p>
              ) : null}
              {operatorSurface.app_menu?.label ? (
                <p className="mt-2 text-sm">
                  <span className="font-medium">App menu:</span>{" "}
                  {operatorSurface.app_menu.label}
                  {operatorSurface.app_menu.technical_name ? (
                    <span className="font-mono text-xs text-muted">
                      {" "}
                      ({operatorSurface.app_menu.technical_name})
                    </span>
                  ) : null}
                </p>
              ) : null}
              {operatorSurface.host_buttons.length > 0 ? (
                <div className="mt-2">
                  <p className="text-sm font-medium">Smart buttons on stock apps</p>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                    {operatorSurface.host_buttons.map((b) => (
                      <li key={`${b.host_model}:${b.residual_model}:${b.button_label}`}>
                        «{b.button_label}» on {b.host_label}{" "}
                        <span className="font-mono text-xs text-muted">
                          ({b.host_model})
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {operatorSurface.residual_buttons.length > 0 ? (
                <div className="mt-2">
                  <p className="text-sm font-medium">Smart buttons on this app</p>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                    {operatorSurface.residual_buttons.map((b) => (
                      <li key={`${b.on_model}:${b.related_model}:${b.button_label}`}>
                        «{b.button_label}» on{" "}
                        <span className="font-mono text-xs">{b.on_model}</span> →{" "}
                        <span className="font-mono text-xs">{b.related_model}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {operatorSurface.stock_links.length > 0 ? (
                <div className="mt-2">
                  <p className="text-sm font-medium">Stock links on the form</p>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                    {operatorSurface.stock_links.map((l) => (
                      <li key={`${l.on_model}:${l.field}`}>
                        {l.field_label} → {l.stock_label}{" "}
                        <span className="font-mono text-xs text-muted">
                          ({l.stock_model})
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1 text-xs text-muted">
                    These stay as form fields — not duplicate smart buttons next to the
                    many2one.
                  </p>
                </div>
              ) : null}
            </Callout>
          ) : null}
          {stockReuse && stockApps.length > 0 ? (
            <Callout
              variant="info"
              title="Community apps covering this brief"
              className="mt-2"
              testId="stock-reuse-apps"
            >
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {stockApps.map((app) => (
                  <li key={app.id}>
                    {app.label}{" "}
                    <span className="font-mono text-xs text-muted">({app.id})</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-sm text-muted">
                Empty models/views is the correct ModuleSpec — stock already covers cashiers,
                quotations, and invoices. Completeness 10.0 is hygiene on an empty spec, not
                a shippable custom app.
              </p>
              <Link
                href={jobAutopilotHref}
                className="mt-2 inline-flex text-sm font-medium text-accent underline"
                onClick={() => stashBriefForJobAutopilot()}
              >
                Open Job Autopilot for sandbox install and quote→invoice smoke
              </Link>
            </Callout>
          ) : null}
          {generationEngine?.needs_clarification?.question ? (
            <Callout
              variant="warning"
              title="One question"
              className="mt-2"
              testId="generation-clarify"
            >
              <p className="text-sm">{generationEngine.needs_clarification.question}</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                {(generationEngine.needs_clarification.options || []).map((opt) => (
                  <li key={opt.id}>
                    {opt.label}
                    {generationEngine.needs_clarification?.default_id === opt.id
                      ? " (default)"
                      : ""}
                  </li>
                ))}
              </ul>
            </Callout>
          ) : null}
          {typeof draftScore === "number" ? (
            <Callout
              variant="info"
              title={
                stockReuse
                  ? `Stock coverage — empty ModuleSpec (hygiene ${draftScore.toFixed(1)}/10)${
                      certTierDisplay ? ` · Cert: ${certTierDisplay}` : ""
                    }`
                  : `Completeness: ${draftScore.toFixed(1)}/10${
                      validatorsGreen ? " · validators green" : ""
                    }${goLiveReady ? " · sandbox proven" : ""}${
                      certTierDisplay ? ` · Cert: ${certTierDisplay}` : ""
                    }`
              }
              className="mt-2"
              testId="draft-scorecard-chip"
            >
              {scoreDimensions ? (
                <p className="text-xs text-muted">
                  Domain {scoreDimensions.domain_fit?.toFixed(1) ?? "—"} · Structure{" "}
                  {scoreDimensions.structure?.toFixed(1) ?? "—"} · Semantics{" "}
                  {scoreDimensions.semantics?.toFixed(1) ?? "—"} · UX{" "}
                  {scoreDimensions.ux?.toFixed(1) ?? "—"} · Hygiene{" "}
                  {scoreDimensions.hygiene?.toFixed(1) ?? "—"}
                </p>
              ) : null}
              {certification ? (
                <p className="mt-1 text-xs text-muted" data-testid="certification-chip">
                  Certification {certTierDisplay ?? "—"} — Quality{" "}
                  {typeof certification.quality === "number"
                    ? certification.quality.toFixed(0)
                    : "—"}
                  · Evidence{" "}
                  {typeof certification.evidence === "number"
                    ? certification.evidence.toFixed(0)
                    : "—"}
                  · Risk{" "}
                  {typeof certification.risk === "number"
                    ? certification.risk.toFixed(0)
                    : "—"}
                  {!certShipReady
                    ? stockReuse
                      ? " — empty-spec hygiene is not go-live; Autopilot smoke is the done-bar"
                      : " — completeness 10.0 is not go-live until Cert ≥ Production (and Option A smoke if pending)"
                    : " — promote stays human; Autopilot smoke is a separate job scorecard"}
                </p>
              ) : null}
              {doneBar?.mode ? (
                <p className="mt-1 text-xs text-muted" data-testid="done-bar-chip">
                  Done-bar: {doneBar.mode}
                  {doneBar.next_step ? ` — ${doneBar.next_step}` : ""}
                </p>
              ) : null}
              <ul
                className="mt-2 list-disc space-y-1 pl-5 text-[11px] text-muted"
                data-testid="score-bars-legend"
              >
                <li>{SCORE_BARS.completeness}</li>
                <li>{SCORE_BARS.certification}</li>
                <li>{SCORE_BARS.autopilot}</li>
              </ul>
              {Array.isArray(scorecard?.findings) && scorecard.findings.length > 0 ? (
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                  {scorecard.findings.slice(0, 6).map((f, i) => (
                    <li key={`${f.element}-${i}`}>
                      {f.dimension ? (
                        <span className="text-muted">{f.dimension}: </span>
                      ) : null}
                      {f.element}: {f.detail}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm">
                  {stockReuse
                    ? "Empty spec is correct. Open Job Autopilot for sandbox install and quote→invoice RPC smoke. Completeness ≠ Cert ≠ Autopilot. Promote stays human."
                    : certShipReady && goLiveReady
                    ? "Sandbox proven + Certification Production/Gold — ready for human promote."
                    : certShipReady
                      ? "Certification Production/Gold — review before promote."
                      : draftScore >= 9.5 && !certShipReady
                        ? "High completeness — not shippable until Certification ≥ Production."
                        : "No major findings — ready for review."}
                </p>
              )}
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="mt-2"
                disabled={aiBusy || !aiDraft || refuseClone}
                data-testid="expert-review-fix"
                onClick={() => void askExpertReviewDraft(true)}
              >
                Ask the Expert to review and fix
              </Button>
              <p className="mt-1 text-[11px] text-muted" data-testid="expert-review-fix-hint">
                {expertCloserHint(aiDraft)}
              </p>
              {!stockReuse && !aiDraft?._component && draftScore >= 9 ? (
                <div className="mt-3 space-y-2" data-testid="elite-promote-workflow">
                  <p className="text-xs text-muted">
                    Optional installable module (Python, mail, cron, tests). Not required to
                    view the app — Apply to Odoo / Open ModuleSpec already generate the UI.
                    Use this path when you want a zip, sandbox install, then promote.
                  </p>
                  {eliteLintNote ? (
                    <p
                      className={`text-xs ${eliteLintOk === false ? "text-warning" : "text-muted"}`}
                      data-testid="elite-lint-note"
                    >
                      {eliteLintNote}
                    </p>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={!aiDraft || eliteBusy}
                      onClick={() => void refreshEliteLint()}
                    >
                      Lint Python blocks
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      loading={eliteBusy}
                      disabled={!aiDraft || eliteBusy || !finisherComplete}
                      data-testid="elite-validate-module"
                      onClick={() => void onEliteValidateModule()}
                    >
                      Validate module (sandbox)
                    </Button>
                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      disabled={!eliteValidationId || !eliteZipBase64 || eliteBusy}
                      data-testid="elite-promote-module"
                      onClick={() => setElitePromoteConfirmOpen(true)}
                    >
                      Promote module
                    </Button>
                    {eliteZipBase64 && aiDraft ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        data-testid="elite-download-zip"
                        onClick={() =>
                          downloadEliteZipBase64(
                            String(aiDraft.technical_name || "custom_module"),
                            eliteZipBase64,
                          )
                        }
                      >
                        Download validated zip
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      data-testid="expert-ask-draft"
                      onClick={() =>
                        openExpert({
                          question: `Review this draft module spec for production readiness: ${draftSummary ?? "module"}. What should I verify before promote?`,
                          freshThread: true,
                        })
                      }
                    >
                      Ask Expert about draft
                    </Button>
                  </div>
                </div>
              ) : null}
              {eliteNote ? <p className="mt-2 text-sm text-muted">{eliteNote}</p> : null}
              {expertReviewNote ? (
                <p className="mt-2 text-sm text-muted">{expertReviewNote}</p>
              ) : null}
              {expertReviewFindings.some((f) => f.narrative_paragraph) ? (
                <div className="mt-3 space-y-3" data-testid="expert-review-narratives">
                  {expertReviewFindings
                    .filter((f) => f.narrative_paragraph)
                    .slice(0, 5)
                    .map((f) => (
                      <div key={f.priority} className="rounded-md border border-border-subtle p-2">
                        <p className="text-xs font-medium text-ink">{f.summary}</p>
                        <p className="mt-1 text-sm text-muted">{f.narrative_paragraph}</p>
                      </div>
                    ))}
                </div>
              ) : null}
            </Callout>
          ) : null}
          {draftNeedsRegenerate && !llmStatusBanner && !stockReuse ? (
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
          {aiWarnings.filter((w) => {
            if (w.startsWith("senior: ")) return false;
            if (w.startsWith("live_apply:") && !w.toLowerCase().includes("gap")) return false;
            return true;
          }).length > 0 ? (
            <Callout variant="warning" title="Draft warnings" className="mt-2">
              <ul className="list-disc space-y-1 pl-5">
                {aiWarnings
                  .filter((w) => {
                    if (w.startsWith("senior: ")) return false;
                    if (w.startsWith("live_apply:") && !w.toLowerCase().includes("gap"))
                      return false;
                    return true;
                  })
                  .slice(0, 12)
                  .map((w, i) => (
                  <li key={`${i}-${w}`}>{w}</li>
                ))}
              </ul>
            </Callout>
          ) : null}
          {authoredOptionA ? (
            <Callout
              variant={authoringPassed ? "info" : "warning"}
              title={
                authoringPassed
                  ? "Authoring gate passed — zip and sandbox unlocked"
                  : "LLM-authored module locked until the gate passes"
              }
              className="mt-2"
              data-testid="option-a-authoring-gate"
            >
              <p className="text-sm">
                Completeness is not this bar. Zip download and sandbox install stay
                disabled until lint, policy (no invented taxes, no SSRF, no secrets),
                and a dry structural zip pass. Promote stays human.
              </p>
              {hostInstallOffers.length > 0 ? (
                <HostInstallPanel
                  offers={hostInstallOffers}
                  busy={aiBusy}
                  disabled={aiBusy || isOdooOnline}
                  disabledReason={
                    isOdooOnline
                      ? "Odoo Online cannot install Community apps from here"
                      : undefined
                  }
                  onInstall={(offer, phrase) => void installAuthoredHostModule(offer, phrase)}
                />
              ) : null}
              {leftoverAuthoringFindings.length > 0 ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                  {leftoverAuthoringFindings.slice(0, 8).map((row, i) => (
                    <li key={`auth-${i}`}>
                      {row.code ? `${row.code}: ` : ""}
                      {row.message}
                      {row.file ? ` (${row.file})` : ""}
                    </li>
                  ))}
                </ul>
              ) : null}
            </Callout>
          ) : null}
          {Array.isArray((aiDraft?._live_apply as { option_a?: string[] } | undefined)?.option_a) &&
          ((aiDraft?._live_apply as { option_a?: string[] }).option_a?.length ?? 0) > 0 ? (
            <Callout
              variant={goLiveReady ? "info" : "warning"}
              title={
                goLiveReady
                  ? "Option A sandbox proven — promote stays human"
                  : Boolean(aiDraft?._capability_primary_option_a)
                    ? "Option A required — not a form-field pack"
                    : "Option A surfaces in this draft"
              }
              className="mt-2"
              data-testid="option-a-gaps"
            >
              <p className="text-sm">
                {Boolean(aiDraft?._capability_primary_option_a)
                  ? "This prompt needs a QWeb/PDF module (sandbox → promote). The draft zip scaffolds Pay now + QR. Live Apply only lands Char stubs — run Sandbox install & smoke to lift the scorecap."
                  : "Some requested surfaces need an installable module. Live Apply still works for metadata; finish Option A separately."}
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                {((aiDraft?._live_apply as { option_a?: string[] }).option_a ?? [])
                  .slice(0, 8)
                  .map((line, i) => (
                    <li key={`oa-${i}`}>{line}</li>
                  ))}
              </ul>
              {Boolean(aiDraft?._capability_primary_option_a) ? (
                <div className="mt-3 space-y-2">
                  <Button
                    type="button"
                    size="sm"
                    disabled={aiBusy || optionAProveBusy || !aiDraft || zipLocked}
                    data-testid="option-a-prove"
                    title={
                      zipLocked
                        ? "Authoring gate has not passed — sandbox stays locked"
                        : undefined
                    }
                    onClick={() => void proveOptionASandbox()}
                  >
                    {optionAProveBusy ? "Sandbox smoke…" : "Sandbox install & smoke"}
                  </Button>
                  {optionAProveNote ? (
                    <p className="text-xs text-muted" data-testid="option-a-prove-note">
                      {optionAProveNote}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </Callout>
          ) : null}
          {Array.isArray(aiDraft?._compute_suggestions) &&
          (aiDraft._compute_suggestions as Array<{ model?: string; message?: string }>)
            .length > 0 ? (
            <div className="mt-2 space-y-2" data-testid="compute-suggestions">
              {(
                aiDraft._compute_suggestions as Array<{ model?: string; message?: string }>
              ).map((s, i) => (
                <Callout
                  key={`${s.model ?? "line"}-${i}`}
                  variant="info"
                  title="Line total suggestion"
                >
                  <p className="text-sm">{s.message}</p>
                  <Link
                    href={`/connections/${connectionId}/automations`}
                    className="mt-2 inline-block text-sm text-accent underline"
                  >
                    Configure equation compute (advanced — confirm before apply)
                  </Link>
                </Callout>
              ))}
            </div>
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
              {residualPreview || aiDraft ? (
                <div className="mt-3" data-testid="stage-h-form-preview">
                  <p className="mb-2 text-xs uppercase tracking-wide text-muted">
                    Review the header form
                  </p>
                  <DraftOdooPreview
                    draft={aiDraft}
                    breadcrumb="Draft Wizard"
                    formPreview={residualPreview}
                  />
                </div>
              ) : null}
              {optionASettings ? (
                <Callout
                  variant="info"
                  title={`Option A settings · ${optionASettings.model}`}
                  className="mt-3"
                  testId="option-a-settings-pane"
                >
                  <p className="text-sm text-muted">
                    These toggles inherit stock POS / document hosts. This is not a live
                    thermal studio and not an x_receipt app.
                  </p>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                    {optionASettings.fields.map((f) => (
                      <li key={f.name}>
                        <span className="font-mono text-xs">{f.name}</span>
                        {f.string ? ` — ${f.string}` : ""}
                        {f.help ? <span className="text-muted"> ({f.help})</span> : null}
                      </li>
                    ))}
                  </ul>
                </Callout>
              ) : null}
              {Boolean(aiDraft._component) || (aiDraft.grain && aiDraft.grain !== "full_app") ? (
                <p className="mt-3 text-sm text-ink">
                  Extends{" "}
                  <span className="font-medium">
                    {String(
                      (aiDraft.connect_points as { host_label?: string } | undefined)
                        ?.host_label ||
                        (aiDraft.connect_points as { host_model?: string } | undefined)
                          ?.host_model ||
                        "a stock app",
                    )}
                  </span>
                  <span className="text-muted">
                    {" "}
                    (
                    {String(
                      (aiDraft.connect_points as { host_model?: string } | undefined)
                        ?.host_model || "?",
                    )}
                    ) — custom models only if the prompt asked for a register or checklist.
                    Nothing writes to Odoo until Apply.
                  </span>
                </p>
              ) : stockReuse ? (
                <p className="mt-3 text-sm text-ink" data-testid="stock-reuse-surface">
                  {stockApps.length
                    ? stockApps.map((app) => app.label).join(" · ")
                    : "Named Community apps"}{" "}
                  — no custom models, views, or smart buttons. Use Job Autopilot.
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
                          connectionId={connectionId}
                          draft={aiDraft ?? undefined}
                          userPrompt={nlPrompt.trim()}
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
      <ConfirmDialog
        open={elitePromoteConfirmOpen}
        title="Promote validated module"
        warning="Installs the sandbox-validated Python module on this live Odoo connection."
        risks={[
          "Adds models, fields, views, Python code, reports, and cron jobs",
          "Uninstall may not fully reverse data",
          "Only promote after sandbox validation passed",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={eliteBusy}
        onCancel={() => setElitePromoteConfirmOpen(false)}
        onConfirm={(phrase) => void onElitePromoteModule(phrase)}
      />
      <ConfirmDialog
        open={walkthroughConfirmOpen}
        title="Load demo walkthrough"
        warning="Creates sample records on this live Odoo so Operations / smart buttons are not empty."
        risks={[
          "Writes data rows on custom x_* models (named Walkthrough …)",
          "Links site, party, job, booking, and equipment lines when those models exist",
          "Reuses the first Contact / Employee / Currency if the spec points at them",
          "Prefer a sandbox connection before production",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setWalkthroughConfirmOpen(false)}
        onConfirm={(phrase) => void onSeedWalkthrough(phrase)}
      />
    </div>
  );
}
