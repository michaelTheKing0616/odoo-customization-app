"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
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
import { useShell } from "@/context/ShellContext";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { reportApiError, isApiNotFound } from "@/lib/api-error";
import { Skeleton } from "@/components/ui/layout-primitives";
import { DraftStudioApplyBar } from "@/components/draft-studio/DraftStudioApplyBar";
import { DraftStudioHonestyBanners } from "@/components/draft-studio/DraftStudioHonestyBanners";
import { DraftStudioIdentityCard } from "@/components/draft-studio/DraftStudioIdentityCard";
import { DraftStudioPreviewPane } from "@/components/draft-studio/DraftStudioPreviewPane";
import { DraftStudioProgress } from "@/components/draft-studio/DraftStudioProgress";
import { DraftStudioPromptPanel } from "@/components/draft-studio/DraftStudioPromptPanel";
import { DraftStudioReviewLayout } from "@/components/draft-studio/DraftStudioReviewLayout";
import { DraftStudioScorecard } from "@/components/draft-studio/DraftStudioScorecard";
import { DraftStudioShell } from "@/components/draft-studio/DraftStudioShell";
import { DraftStudioTemplates } from "@/components/draft-studio/DraftStudioTemplates";
import { odooMenuUrl, odooViewUrl } from "@/lib/odoo-urls";
import { JobPollError, pollJob } from "@/lib/jobs";
import {
  draftFromJobResult,
  pickRecoverableDraft,
  resolveJobDraftOutcome,
  successNoteForDraft,
  visibleDraftWarnings,
} from "@/lib/draft-job-outcome";
import {
  autoWiredReuseDecisions,
  confirmedReuseModelsFromDraft,
  inferredReuseSuggestions as inferredReuseFromDraft,
  installableReuseSuggestions as installableReuseFromDraft,
} from "@/lib/reuse-chips";
import {
  briefTextForJobAutopilot,
  stashJobAutopilotBrief,
} from "@/lib/job-brief-handoff";
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
  llmStatusBannerCopy,
  llmStatusFromDraft,
  showRetryEnrichment,
  withEnrichmentCleanFlags,
} from "@/lib/draft-llm-status";
import { operatorSurfaceFromDraft } from "@/lib/operator-surface";
import {
  certificationFromDraft,
  doneBarFromDraft,
  draftNeedsRegenerate,
  draftStudioJourneyFromState,
  goLiveReadyFromDraft,
  scorecardFromDraft,
} from "@/lib/draft-studio-journey";
import "@/styles/studio-refinement.css";

const CONFIRM_PHRASE = "I understand the risks";

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
  const needsRegenerate = draftNeedsRegenerate(aiDraft, aiWarnings);
  const llmStatus = llmStatusFromDraft(aiDraft);
  const llmStatusMode = llmStatus?.mode;
  const scorecard = scorecardFromDraft(aiDraft);
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
  const doneBar = doneBarFromDraft(aiDraft);
  const goLiveReady = goLiveReadyFromDraft(aiDraft);
  const certification = certificationFromDraft(aiDraft);
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
  const retryAvailable = showRetryEnrichment({
    draft: aiDraft,
    stockReuse,
    refuseClone,
  });
  const retryEnrichmentDisabled = Boolean(
    aiBusy || !aiDraft || draftEnrichmentClean(aiDraft),
  );
  const llmStatusBanner = llmStatusBannerCopy({
    draft: aiDraft,
    stockReuse,
    retryDisabled: retryEnrichmentDisabled,
  });
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


  const inferredReuseSuggestions = useMemo(
    () => inferredReuseFromDraft(aiDraft, rejectedInferredReuse),
    [aiDraft, rejectedInferredReuse],
  );

  const installableReuseSuggestions = useMemo(
    () => installableReuseFromDraft(aiDraft, rejectedInferredReuse),
    [aiDraft, rejectedInferredReuse],
  );

  const autoWiredReuse = useMemo(() => autoWiredReuseDecisions(aiDraft), [aiDraft]);

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

  const journey = draftStudioJourneyFromState({
    generating: aiBusy,
    hasDraft: Boolean(aiDraft),
    applied: Boolean(genUiResult),
  });

  function startNewDraft() {
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
    setError(null);
  }

  const applyBarProps = {
    canDraft: canDraftModule,
    canApply: canGenerateUi,
    hasDraft: Boolean(aiDraft),
    aiBusy,
    busy,
    zipBusy,
    finisherComplete,
    refuseClone,
    stockReuse,
    moduleDelivery,
    zipLocked,
    generateUiBlocked,
    overlapPending: overlapFindings.length > 0 && !overlapResolved,
    needsConnectReview,
    connectApproved: connectPointsApproved,
    designerHref,
    designerModel,
    jobAutopilotHref,
    applied: Boolean(genUiResult),
    onCreateDraft: () => void onDraftFromPrompt(),
    onApply: () => void onPrepareGenerateUi(),
    onDownloadZip: () => void onDownloadModuleZip(),
    onOpenModuleSpec: () => openModuleSpecEditor(),
    onStashJobBrief: () => stashBriefForJobAutopilot(),
  };

  const reuseProps = {
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
    onToggleReuse: toggleReuse,
    onSearch: setReuseSearch,
    onReloadCatalog: () => void reloadReuseCatalog(),
    onConfirmInferred: (model: string) => void confirmInferredReuse(model),
    onRejectInferred: (model: string) => void rejectInferredReuse(model),
    onConfirmInstallable: (model: string) => void confirmInstallableReuse(model),
    onRejectInstallable: (model: string) => void rejectInstallableReuse(model),
  };

  const promptPanel = (
    <DraftStudioPromptPanel
      connectionId={connectionId}
      nlPrompt={nlPrompt}
      aiEnabled={aiEnabled}
      aiProviderLabel={aiProviderLabel}
      ollamaDetail={ollamaDetail}
      grainOverride={grainOverride}
      grainLabel={grainLabel}
      jsonPasteOpen={jsonPasteOpen}
      jsonPaste={jsonPaste}
      jsonBusy={busy && aiBusyLabel === "Preparing JSON draft…"}
      busy={busy}
      overlapFindings={overlapFindings}
      overlapChoice={overlapChoice}
      overlapBusy={overlapBusy}
      overlapResolved={overlapResolved}
      connectPoints={connectPoints}
      needsConnectReview={needsConnectReview}
      connectPointsApproved={connectPointsApproved}
      connectReviewBusy={connectReviewBusy}
      hostCandidates={hostCandidates}
      gallery={componentGallery}
      selectedGalleryId={selectedGalleryId}
      showStudioBridge={Boolean(
        operatorBrief?.ir_confidence === "low" ||
          generationEngine?.needs_clarification?.question,
      )}
      hasDraft={Boolean(aiDraft)}
      isFullAppGrain={isFullAppGrain}
      showActions={journey.id === "prompt"}
      applyBar={applyBarProps}
      reuse={reuseProps}
      onPromptChange={(value) => {
        setNlPrompt(value);
        setConnectPointsApproved(false);
        setConnectPoints(null);
        setOverlapFindings([]);
        setOverlapChoice(null);
        setOverlapFindingId(null);
      }}
      onToggleJson={() => setJsonPasteOpen((v) => !v)}
      onJsonChange={setJsonPaste}
      onLoadJson={() => void onLoadPastedJson("paste")}
      onUploadJson={(file) => void onLoadPastedJson("file", file)}
      onGrainChange={(value) => {
        setGrainOverride(value);
        setConnectPointsApproved(value === "full_app");
        setConnectPoints(null);
      }}
      onOverlapUse={onOverlapUse}
      onOverlapExtend={onOverlapExtend}
      onOverlapBuildAnyway={(id) => onOverlapBuildAnyway(id)}
      onConnectField={(key, value) => {
        setConnectPoints({ ...(connectPoints || {}), [key]: value });
        setConnectPointsApproved(false);
      }}
      onApproveConnect={() => setConnectPointsApproved(true)}
      onReviewConnect={() => void onReviewConnectPoints()}
      onCheckOverlap={() => void onCheckOverlap()}
      onSelectGallery={(c) => {
        setSelectedGalleryId(c.id);
        setNlPrompt(`Add ${c.name.toLowerCase()} to my ${c.host_slot.replace(".", " ")}s`);
        setConnectPointsApproved(false);
        setConnectPoints(null);
      }}
      onClear={startNewDraft}
    />
  );

  return (
    <DraftStudioShell
      connectionId={connectionId}
      connectionName={connection?.name}
      journey={journey}
      canvas={journey.id === "review" || journey.id === "apply"}
      hasDraft={Boolean(aiDraft)}
      onStartNew={startNewDraft}
    >
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
      {loading ? (
        <div className="mt-4 space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : null}
      {error ? <ErrorNotice message={error} className="mt-4" /> : null}

      {journey.id === "prompt" ? (
        <>
          <DraftStudioIdentityCard
            displayName={displayName}
            technicalPrefix={technicalPrefix}
            multiCompany={multiCompany}
            onDisplayName={setDisplayName}
            onTechnicalPrefix={setTechnicalPrefix}
            onMultiCompany={setMultiCompany}
          />
          {promptPanel}
          <DraftStudioTemplates
            connectionId={connectionId}
            connection={connection}
            templates={templates}
            selectedId={selected?.id}
            result={result}
            onOpenTemplate={openConfirm}
            templateScaffoldOpts={templateScaffoldOpts}
          />
        </>
      ) : null}

      {journey.id === "enrich" ? (
        <DraftStudioProgress label={aiBusyLabel || "Creating draft…"} />
      ) : null}

      {(journey.id === "review" || journey.id === "apply") && aiDraft ? (
        <div className="studio-review">
          <DraftStudioHonestyBanners
            connectionId={connectionId}
            liveApplyBanner={liveApplyBanner}
            unfinishedBanner={unfinishedBanner}
            generateUiBlocked={generateUiBlocked}
            aiNote={aiNote}
            genUiResult={genUiResult}
            odooAppUrl={odooAppUrl}
            llmStatusBanner={llmStatusBanner}
            llmStatusMode={llmStatusMode}
            retryDisabled={retryEnrichmentDisabled}
            showRetry={retryAvailable}
            aiBusy={aiBusy}
            operatorBrief={operatorBrief}
            refuseClone={refuseClone}
            refuseHonesty={generationEngine?.honesty}
            generationHonesty={generationEngine?.honesty}
            operatorSurface={operatorSurface}
            stockReuse={stockReuse}
            stockApps={stockApps}
            jobAutopilotHref={jobAutopilotHref}
            clarifyQuestion={generationEngine?.needs_clarification?.question}
            clarifyOptions={generationEngine?.needs_clarification?.options}
            clarifyDefaultId={generationEngine?.needs_clarification?.default_id}
            draftNeedsRegenerate={needsRegenerate}
            canDraft={canDraftModule}
            warnings={visibleDraftWarnings(aiWarnings)}
            authoredOptionA={authoredOptionA}
            authoringPassed={authoringPassed}
            hostInstallOffers={hostInstallOffers}
            leftoverAuthoringFindings={leftoverAuthoringFindings}
            isOdooOnline={Boolean(isOdooOnline)}
            optionALines={liveApply?.option_a ?? []}
            capabilityPrimaryOptionA={Boolean(aiDraft._capability_primary_option_a)}
            goLiveReady={goLiveReady}
            zipLocked={zipLocked}
            optionAProveBusy={optionAProveBusy}
            optionAProveNote={optionAProveNote}
            computeSuggestions={
              Array.isArray(aiDraft._compute_suggestions)
                ? (aiDraft._compute_suggestions as Array<{ model?: string; message?: string }>)
                : []
            }
            refusals={aiRefusals}
            snapshots={draftCacheEntries}
            onRetryEnrichment={() => void retryAiEnrichment()}
            onRegenerate={() => void onDraftFromPrompt()}
            onStashJobBrief={() => stashBriefForJobAutopilot()}
            onInstallHost={(offer, phrase) => void installAuthoredHostModule(offer, phrase)}
            onProveOptionA={() => void proveOptionASandbox()}
            onRestoreSnapshot={(id) => void restoreDraftFromCache(id)}
            onLoadWalkthrough={() => setWalkthroughConfirmOpen(true)}
          />
          <DraftStudioReviewLayout
            header={
              <div className="panel-header">
                <div className="breadcrumb">
                  <span>{String(aiDraft.display_name || aiDraft.technical_name || "Draft")}</span>
                  <span aria-hidden>›</span>
                  <span className="current">{residualPreview?.title || "Form preview"}</span>
                </div>
              </div>
            }
            preview={
              <DraftStudioPreviewPane
                connectionId={connectionId}
                draft={aiDraft}
                preview={residualPreview}
                optionASettings={optionASettings}
                stockReuse={stockReuse}
                stockApps={stockApps}
                nlPrompt={nlPrompt}
              />
            }
            chrome={
              <DraftStudioScorecard
                scorecard={scorecard}
                certification={certification}
                certTierDisplay={certTierDisplay}
                certShipReady={certShipReady}
                doneBar={doneBar}
                goLiveReady={goLiveReady}
                stockReuse={stockReuse}
                isComponent={Boolean(aiDraft._component)}
                refuseClone={refuseClone}
                aiBusy={aiBusy}
                hasDraft
                expertHint={expertCloserHint(aiDraft)}
                eliteBusy={eliteBusy}
                eliteLintOk={eliteLintOk}
                eliteLintNote={eliteLintNote}
                eliteValidationId={eliteValidationId}
                eliteZipBase64={eliteZipBase64}
                eliteNote={eliteNote}
                expertReviewNote={expertReviewNote}
                expertReviewFindings={expertReviewFindings}
                finisherComplete={finisherComplete}
                draftSummary={draftSummary}
                onExpertFix={() => void askExpertReviewDraft(true)}
                onLint={() => void refreshEliteLint()}
                onValidate={() => void onEliteValidateModule()}
                onPromote={() => setElitePromoteConfirmOpen(true)}
                onDownloadValidatedZip={() =>
                  downloadEliteZipBase64(
                    String(aiDraft.technical_name || "custom_module"),
                    eliteZipBase64 || "",
                  )
                }
                onAskExpert={() =>
                  openExpert({
                    question: `Review this draft module spec for production readiness: ${draftSummary ?? "module"}. What should I verify before promote?`,
                    freshThread: true,
                  })
                }
              />
            }
            footer={<DraftStudioApplyBar {...applyBarProps} />}
          />
          <details className="draft-studio-disclosure mt-6">
            <summary className="cursor-pointer text-sm font-medium text-muted">
              Adjust prompt
            </summary>
            <div className="mt-3">{promptPanel}</div>
          </details>
        </div>
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
    </DraftStudioShell>
  );
}
