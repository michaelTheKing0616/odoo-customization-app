"use client";

import { api } from "@/lib/api";
import { reportApiError } from "@/lib/api-error";
import {
  draftEnrichmentClean,
  withEnrichmentCleanFlags,
} from "@/lib/draft-llm-status";
import {
  draftFromJobResult,
  pickRecoverableDraft,
  resolveJobDraftOutcome,
  successNoteForDraft,
} from "@/lib/draft-job-outcome";
import { JobPollError } from "@/lib/jobs";
import {
  mapDraftCacheEntries,
  pollBackgroundJob,
  type DraftCacheEntry,
} from "./wizard-helpers";

type UseWizardDraftArgs = {
  connectionId: string;
  nlPrompt: string;
  aiDraft: Record<string, unknown> | null;
  canDraftModule: boolean;
  rejectedInferredReuse: string[];
  reuseModels: string[];
  grainOverride: string;
  selectedGalleryId: string;
  connectPoints: Record<string, unknown> | null;
  overlapChoice: string | null;
  overlapFindingId: string | null;
  setNlPrompt: (value: string) => void;
  setAiDraft: (value: Record<string, unknown> | null) => void;
  setAiBusy: (value: boolean) => void;
  setAiBusyLabel: (value: string | null) => void;
  setError: (value: string | null) => void;
  setAiNote: (value: string | null) => void;
  setAiWarnings: (value: string[]) => void;
  setAiRefusals: (value: import("@/lib/api").ProtectedModuleRefusal[]) => void;
  setGenUiResult: (value: string | null) => void;
  setDraftCacheEntries: (value: DraftCacheEntry[]) => void;
  setGrainLabel: (value: string | null) => void;
  setEffectiveGrain: (value: string) => void;
  setConnectPoints: (value: Record<string, unknown> | null) => void;
  setHostCandidates: (
    value: Array<{ model: string; label: string; score: number; reason?: string }>,
  ) => void;
  setConnectPointsApproved: (value: boolean) => void;
  setOverlapFindings: (value: import("./wizard-helpers").OverlapFinding[]) => void;
  setOverlapChoice: (value: string | null) => void;
  setOverlapFindingId: (value: string | null) => void;
  setOdooAppUrl: (value: string | null) => void;
  setValidateLiveResult: (value: import("@/lib/api").ValidateLiveResult | null) => void;
};

export function useWizardDraft({
  connectionId,
  nlPrompt,
  aiDraft,
  canDraftModule,
  rejectedInferredReuse,
  reuseModels,
  grainOverride,
  selectedGalleryId,
  connectPoints,
  overlapChoice,
  overlapFindingId,
  setNlPrompt,
  setAiDraft,
  setAiBusy,
  setAiBusyLabel,
  setError,
  setAiNote,
  setAiWarnings,
  setAiRefusals,
  setGenUiResult,
  setDraftCacheEntries,
  setGrainLabel,
  setEffectiveGrain,
  setConnectPoints,
  setHostCandidates,
  setConnectPointsApproved,
  setOverlapFindings,
  setOverlapChoice,
  setOverlapFindingId,
  setOdooAppUrl,
  setValidateLiveResult,
}: UseWizardDraftArgs) {
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
        setDraftCacheEntries(mapDraftCacheEntries(listed));
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
      setDraftCacheEntries(mapDraftCacheEntries(cached));
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
        setDraftCacheEntries(mapDraftCacheEntries(listed));
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

  return {
    retryAiEnrichment,
    onDraftFromPrompt,
    startNewDraft,
  };
}
