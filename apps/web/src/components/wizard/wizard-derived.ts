import {
  displayedCertificationTier,
  expertCloserHint,
  liveApplyGapBanner,
  unfinishedDraftBanner,
} from "@/lib/draft-studio-banners";
import {
  authoringFindingsWithoutHostInstall,
  draftFinisherComplete,
  generationEngineFromDraft,
  hostInstallOffersFromDraft,
  isOptionAAuthoredDraft,
  isRefuseCloneDraft,
  isStockReuseDraft,
  optionAAuthoringPassed,
  optionASettingsFromDraft,
  residualFormPreviewFromDraft,
  stockAppsFromDraft,
  wantsModuleDelivery,
} from "@/lib/draft-form-preview";
import {
  certificationFromDraft,
  doneBarFromDraft,
  draftNeedsRegenerate,
  draftStudioJourneyFromState,
  goLiveReadyFromDraft,
  scorecardFromDraft,
} from "@/lib/draft-studio-journey";
import {
  draftEnrichmentClean,
  llmStatusBannerCopy,
  llmStatusFromDraft,
  showRetryEnrichment,
} from "@/lib/draft-llm-status";
import { operatorSurfaceFromDraft } from "@/lib/operator-surface";
import { primaryCustomModelFromDraft, viewDesignerHref } from "@/lib/draft-models";
import type { Connection } from "@/lib/api";
import type { LiveApplyState, OperatorBriefState } from "./wizard-helpers";

export function deriveWizardFields(args: {
  connectionId: string;
  connection: Connection | null;
  aiDraft: Record<string, unknown> | null;
  aiWarnings: string[];
  aiBusy: boolean;
  genUiResult: string | null;
  grainOverride: string;
  grainLabel: string | null;
  effectiveGrain: string;
  overlapFindingsLength: number;
  overlapChoice: string | null;
  connectPointsApproved: boolean;
  connectPoints: Record<string, unknown> | null;
  nlPrompt: string;
}) {
  const {
    connectionId,
    connection,
    aiDraft,
    aiWarnings,
    aiBusy,
    genUiResult,
    grainOverride,
    grainLabel,
    effectiveGrain,
    overlapFindingsLength,
    overlapChoice,
    connectPointsApproved,
    connectPoints,
    nlPrompt,
  } = args;

  const draftSummary = aiDraft
    ? String(aiDraft.display_name ?? aiDraft.technical_name ?? "draft")
    : undefined;
  const needsRegenerate = draftNeedsRegenerate(aiDraft, aiWarnings);
  const llmStatus = llmStatusFromDraft(aiDraft);
  const llmStatusMode = llmStatus?.mode;
  const scorecard = scorecardFromDraft(aiDraft);
  const finisherComplete = draftFinisherComplete(aiDraft);
  const liveApplyBanner = liveApplyGapBanner(aiDraft);
  const liveApply = aiDraft?._live_apply as LiveApplyState | undefined;
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
  const certTierDisplay = displayedCertificationTier(aiDraft);
  const certShipReady =
    (certTierDisplay === "Production" || certTierDisplay === "Gold") &&
    !certification?.option_a_pending &&
    !stockReuse;
  const operatorBrief = aiDraft?._operator_brief as OperatorBriefState | undefined;
  const moduleDelivery = wantsModuleDelivery(aiDraft);
  const residualPreview = residualFormPreviewFromDraft(aiDraft);
  const optionASettings = optionASettingsFromDraft(aiDraft);
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
  const unfinishedBanner = unfinishedDraftBanner(aiDraft, { generating: aiBusy });
  const resolvedGrain = grainOverride || effectiveGrain;
  const isFullAppGrain =
    resolvedGrain === "full_app" || grainLabel?.toLowerCase() === "full app";
  const isComponentGrain =
    !isFullAppGrain &&
    (resolvedGrain === "feature_slice" || resolvedGrain === "field_pack");
  const needsConnectReview = isComponentGrain;
  const overlapResolved =
    overlapFindingsLength === 0 || overlapChoice === "build_anyway" || overlapChoice === "use";
  const canDraftModule =
    nlPrompt.trim().length >= 3 &&
    overlapResolved &&
    (!needsConnectReview || (connectPointsApproved && connectPoints !== null));
  const journey = draftStudioJourneyFromState({
    generating: aiBusy,
    hasDraft: Boolean(aiDraft),
    applied: Boolean(genUiResult),
  });

  return {
    draftSummary,
    needsRegenerate,
    llmStatusMode,
    scorecard,
    finisherComplete,
    liveApplyBanner,
    liveApply,
    doneBar,
    goLiveReady,
    certification,
    generationEngine,
    refuseClone,
    stockReuse,
    authoredOptionA,
    authoringPassed,
    hostInstallOffers,
    leftoverAuthoringFindings,
    zipLocked,
    isOdooOnline,
    stockApps,
    operatorSurface,
    jobAutopilotHref,
    designerHref,
    designerModel,
    certTierDisplay,
    certShipReady,
    operatorBrief,
    moduleDelivery,
    residualPreview,
    optionASettings,
    retryAvailable,
    retryEnrichmentDisabled,
    llmStatusBanner,
    unfinishedBanner,
    resolvedGrain,
    isFullAppGrain,
    isComponentGrain,
    needsConnectReview,
    overlapResolved,
    canDraftModule,
    journey,
    expertHint: expertCloserHint(aiDraft),
  };
}
