"use client";

import { useMemo } from "react";
import { type ReuseModelRow } from "@/lib/api";
import {
  scaffoldApplyAllowed,
  scaffoldApplyBlockedReason,
  scaffoldOptsFromSpec,
} from "@/lib/capabilities";
import { useShell } from "@/context/ShellContext";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import {
  briefTextForJobAutopilot,
  stashJobAutopilotBrief,
} from "@/lib/job-brief-handoff";
import { handoffFromDraft, stashBuildSpineHandoff } from "@/lib/build-spine-handoff";
import {
  autoWiredReuseDecisions,
  inferredReuseSuggestions as inferredReuseFromDraft,
  installableReuseSuggestions as installableReuseFromDraft,
} from "@/lib/reuse-chips";
import { useWizardApply } from "./use-wizard-apply";
import { useWizardConnect } from "./use-wizard-connect";
import { useWizardDraft } from "./use-wizard-draft";
import { useWizardExpert } from "./use-wizard-expert";
import { useWizardLoad } from "./use-wizard-load";
import { useWizardReuse } from "./use-wizard-reuse";
import { useWizardScaffold } from "./use-wizard-scaffold";
import { useWizardState } from "./use-wizard-state";
import { deriveWizardFields } from "./wizard-derived";

export function useWizardPage(connectionId: string) {
  const { openExpert } = useShell();
  const s = useWizardState();

  const derived = deriveWizardFields({
    connectionId,
    connection: s.connection,
    aiDraft: s.aiDraft,
    aiWarnings: s.aiWarnings,
    aiBusy: s.aiBusy,
    genUiResult: s.genUiResult,
    grainOverride: s.grainOverride,
    grainLabel: s.grainLabel,
    effectiveGrain: s.effectiveGrain,
    overlapFindingsLength: s.overlapFindings.length,
    overlapChoice: s.overlapChoice,
    connectPointsApproved: s.connectPointsApproved,
    connectPoints: s.connectPoints,
    nlPrompt: s.nlPrompt,
  });

  useSyncShellContext({
    draftSummary: derived.draftSummary,
    route: `/connections/${connectionId}/wizard`,
  });

  function stashBriefForJobAutopilot() {
    const text = briefTextForJobAutopilot(s.aiDraft, s.nlPrompt);
    if (text) stashJobAutopilotBrief(connectionId, text);
    const handoff = handoffFromDraft(
      s.aiDraft && typeof s.aiDraft === "object"
        ? (s.aiDraft as Record<string, unknown>)
        : null,
      s.nlPrompt,
    );
    if (handoff.brief || handoff.delivery_lane) {
      stashBuildSpineHandoff(connectionId, handoff);
    }
  }

  const { reloadReuseCatalog, refreshDraftCacheList } = useWizardLoad({
    connectionId,
    stockReuse: derived.stockReuse,
    aiDraft: s.aiDraft,
    nlPrompt: s.nlPrompt,
    stashBriefForJobAutopilot,
    setLoading: s.setLoading,
    setError: s.setError,
    setConnection: s.setConnection,
    setTemplates: s.setTemplates,
    setComponentGallery: s.setComponentGallery,
    setAiEnabled: s.setAiEnabled,
    setAiProviderLabel: s.setAiProviderLabel,
    setOllamaDetail: s.setOllamaDetail,
    setDraftCacheEntries: s.setDraftCacheEntries,
    setReuseCatalog: s.setReuseCatalog,
    setReuseCatalogStatus: s.setReuseCatalogStatus,
    setReuseCatalogError: s.setReuseCatalogError,
  });

  const connect = useWizardConnect({
    connectionId,
    nlPrompt: s.nlPrompt,
    grainOverride: s.grainOverride,
    connectPoints: s.connectPoints,
    selectedGalleryId: s.selectedGalleryId,
    jsonPaste: s.jsonPaste,
    setError: s.setError,
    setAiNote: s.setAiNote,
    setAiDraft: s.setAiDraft,
    setAiWarnings: s.setAiWarnings,
    setBusy: s.setBusy,
    setAiBusyLabel: s.setAiBusyLabel,
    setOverlapBusy: s.setOverlapBusy,
    setOverlapChoice: s.setOverlapChoice,
    setOverlapFindingId: s.setOverlapFindingId,
    setOverlapFindings: s.setOverlapFindings,
    setGrainOverride: s.setGrainOverride,
    setGrainLabel: s.setGrainLabel,
    setEffectiveGrain: s.setEffectiveGrain,
    setConnectPointsApproved: s.setConnectPointsApproved,
    setConnectReviewBusy: s.setConnectReviewBusy,
    setConnectPoints: s.setConnectPoints,
    setHostCandidates: s.setHostCandidates,
    setSelectedGalleryId: s.setSelectedGalleryId,
    setGenUiResult: s.setGenUiResult,
    setValidateLiveResult: s.setValidateLiveResult,
    setJsonPasteOpen: s.setJsonPasteOpen,
  });

  const draft = useWizardDraft({
    connectionId,
    nlPrompt: s.nlPrompt,
    aiDraft: s.aiDraft,
    canDraftModule: derived.canDraftModule,
    rejectedInferredReuse: s.rejectedInferredReuse,
    reuseModels: s.reuseModels,
    grainOverride: s.grainOverride,
    selectedGalleryId: s.selectedGalleryId,
    connectPoints: s.connectPoints,
    overlapChoice: s.overlapChoice,
    overlapFindingId: s.overlapFindingId,
    setNlPrompt: s.setNlPrompt,
    setAiDraft: s.setAiDraft,
    setAiBusy: s.setAiBusy,
    setAiBusyLabel: s.setAiBusyLabel,
    setError: s.setError,
    setAiNote: s.setAiNote,
    setAiWarnings: s.setAiWarnings,
    setAiRefusals: s.setAiRefusals,
    setGenUiResult: s.setGenUiResult,
    setDraftCacheEntries: s.setDraftCacheEntries,
    setGrainLabel: s.setGrainLabel,
    setEffectiveGrain: s.setEffectiveGrain,
    setConnectPoints: s.setConnectPoints,
    setHostCandidates: s.setHostCandidates,
    setConnectPointsApproved: s.setConnectPointsApproved,
    setOverlapFindings: s.setOverlapFindings,
    setOverlapChoice: s.setOverlapChoice,
    setOverlapFindingId: s.setOverlapFindingId,
    setOdooAppUrl: s.setOdooAppUrl,
    setValidateLiveResult: s.setValidateLiveResult,
  });

  const reuse = useWizardReuse({
    connectionId,
    nlPrompt: s.nlPrompt,
    aiDraft: s.aiDraft,
    reuseModels: s.reuseModels,
    rejectedInferredReuse: s.rejectedInferredReuse,
    reloadReuseCatalog,
    onDraftFromPrompt: draft.onDraftFromPrompt,
    setReuseModels: s.setReuseModels,
    setRejectedInferredReuse: s.setRejectedInferredReuse,
    setAiBusy: s.setAiBusy,
    setAiBusyLabel: s.setAiBusyLabel,
    setError: s.setError,
    setAiDraft: s.setAiDraft,
    setAiWarnings: s.setAiWarnings,
    setAiNote: s.setAiNote,
  });

  const expert = useWizardExpert({
    connectionId,
    nlPrompt: s.nlPrompt,
    aiDraft: s.aiDraft,
    refreshDraftCacheList,
    setNlPrompt: s.setNlPrompt,
    setReuseModels: s.setReuseModels,
    setAiDraft: s.setAiDraft,
    setAiBusy: s.setAiBusy,
    setAiBusyLabel: s.setAiBusyLabel,
    setError: s.setError,
    setAiNote: s.setAiNote,
    setOptionAProveBusy: s.setOptionAProveBusy,
    setOptionAProveNote: s.setOptionAProveNote,
    setExpertReviewNote: s.setExpertReviewNote,
    setExpertReviewFindings: s.setExpertReviewFindings,
  });

  const scaffold = useWizardScaffold({
    connectionId,
    selected: s.selected,
    displayName: s.displayName,
    technicalPrefix: s.technicalPrefix,
    multiCompany: s.multiCompany,
    setSelected: s.setSelected,
    setDisplayName: s.setDisplayName,
    setResult: s.setResult,
    setError: s.setError,
    setConfirmOpen: s.setConfirmOpen,
    setBusy: s.setBusy,
    setAiNote: s.setAiNote,
  });

  const apply = useWizardApply({
    connectionId,
    connection: s.connection,
    multiCompany: s.multiCompany,
    aiDraft: s.aiDraft,
    skipValidateLive: s.skipValidateLive,
    eliteValidationId: s.eliteValidationId,
    eliteZipBase64: s.eliteZipBase64,
    setBusy: s.setBusy,
    setError: s.setError,
    setZipBusy: s.setZipBusy,
    setAiNote: s.setAiNote,
    setEliteLintNote: s.setEliteLintNote,
    setEliteLintOk: s.setEliteLintOk,
    setEliteBusy: s.setEliteBusy,
    setEliteNote: s.setEliteNote,
    setEliteValidationId: s.setEliteValidationId,
    setEliteZipBase64: s.setEliteZipBase64,
    setElitePromoteConfirmOpen: s.setElitePromoteConfirmOpen,
    setGenUiConfirmOpen: s.setGenUiConfirmOpen,
    setGenUiResult: s.setGenUiResult,
    setOdooAppUrl: s.setOdooAppUrl,
    setAiWarnings: s.setAiWarnings,
    setWalkthroughConfirmOpen: s.setWalkthroughConfirmOpen,
    setValidateLiveResult: s.setValidateLiveResult,
    setSkipValidateLive: s.setSkipValidateLive,
  });

  const inferredReuseSuggestions = useMemo(
    () => inferredReuseFromDraft(s.aiDraft, s.rejectedInferredReuse),
    [s.aiDraft, s.rejectedInferredReuse],
  );
  const installableReuseSuggestions = useMemo(
    () => installableReuseFromDraft(s.aiDraft, s.rejectedInferredReuse),
    [s.aiDraft, s.rejectedInferredReuse],
  );
  const autoWiredReuse = useMemo(() => autoWiredReuseDecisions(s.aiDraft), [s.aiDraft]);
  const reuseCatalogByModel = useMemo(() => {
    const map = new Map<string, ReuseModelRow>();
    for (const row of s.reuseCatalog) {
      map.set(row.model, row);
    }
    return map;
  }, [s.reuseCatalog]);
  const filteredReuseCatalog = useMemo(() => {
    const needle = s.reuseSearch.trim().toLowerCase();
    const rows = needle
      ? s.reuseCatalog.filter((row) => {
          const hay = `${row.model} ${row.name} ${row.app}`.toLowerCase();
          return hay.includes(needle);
        })
      : s.reuseCatalog;
    return rows.slice(0, 120);
  }, [s.reuseCatalog, s.reuseSearch]);

  const draftOpts = scaffoldOptsFromSpec(s.aiDraft as Record<string, unknown> | null);
  const canGenerateUi = scaffoldApplyAllowed(s.connection, draftOpts);
  const generateUiBlocked = scaffoldApplyBlockedReason(s.connection, draftOpts);

  const applyBarProps = {
    canDraft: derived.canDraftModule,
    canApply: canGenerateUi,
    hasDraft: Boolean(s.aiDraft),
    aiBusy: s.aiBusy,
    busy: s.busy,
    zipBusy: s.zipBusy,
    finisherComplete: derived.finisherComplete,
    refuseClone: derived.refuseClone,
    stockReuse: derived.stockReuse,
    moduleDelivery: derived.moduleDelivery,
    zipLocked: derived.zipLocked,
    generateUiBlocked,
    overlapPending: s.overlapFindings.length > 0 && !derived.overlapResolved,
    needsConnectReview: derived.needsConnectReview,
    connectApproved: s.connectPointsApproved,
    designerHref: derived.designerHref,
    designerModel: derived.designerModel,
    jobAutopilotHref: derived.jobAutopilotHref,
    applied: Boolean(s.genUiResult),
    onCreateDraft: () => void draft.onDraftFromPrompt(),
    onApply: () => void apply.onPrepareGenerateUi(),
    onDownloadZip: () => void apply.onDownloadModuleZip(),
    onOpenModuleSpec: () => apply.openModuleSpecEditor(),
    onStashJobBrief: () => stashBriefForJobAutopilot(),
  };

  const reuseProps = {
    reuseModels: s.reuseModels,
    reuseCatalog: s.reuseCatalog,
    reuseCatalogByModel,
    filteredReuseCatalog,
    reuseSearch: s.reuseSearch,
    reuseCatalogStatus: s.reuseCatalogStatus,
    reuseCatalogError: s.reuseCatalogError,
    autoWiredReuse,
    inferredReuseSuggestions,
    installableReuseSuggestions,
    aiBusy: s.aiBusy,
    aiBusyLabel: s.aiBusyLabel,
    onToggleReuse: reuse.toggleReuse,
    onSearch: s.setReuseSearch,
    onReloadCatalog: () => void reloadReuseCatalog(),
    onConfirmInferred: (model: string) => void reuse.confirmInferredReuse(model),
    onRejectInferred: (model: string) => void reuse.rejectInferredReuse(model),
    onConfirmInstallable: (model: string) => void reuse.confirmInstallableReuse(model),
    onRejectInstallable: (model: string) => void reuse.rejectInstallableReuse(model),
  };

  return {
    connectionId,
    ...s,
    ...derived,
    canGenerateUi,
    generateUiBlocked,
    applyBarProps,
    reuseProps,
    openExpert,
    stashBriefForJobAutopilot,
    ...connect,
    ...draft,
    ...expert,
    ...reuse,
    ...scaffold,
    ...apply,
  };
}

export type WizardPageModel = ReturnType<typeof useWizardPage>;
