"use client";

import { isOdooOnlineUrl } from "@/lib/odoo-online-url";
import { useMemo } from "react";
import type { Connection } from "@/lib/api";
import {
  scaffoldApplyAllowed,
  scaffoldApplyBlockedReason,
  scaffoldOptsFromSpec,
} from "@/lib/capabilities";
import {
  documentGrammarFromDraft,
  generationEngineFromDraft,
  isGoldOptionADraft,
  isOptionAAuthoredDraft,
  isRefuseCloneDraft,
  isStockReuseDraft,
  optionAAuthoringPassed,
  optionAAuthoringRetryable,
  optionAAuthoringNeedsAutoRepair,
  hostInstallOffersFromDraft,
  authoringFindingsWithoutHostInstall,
  optionASettingsFromDraft,
  residualFormPreviewFromDraft,
  stockAppsFromDraft,
  surfaceGateBlocksInstall,
  surfaceGateFindingsFromDraft,
} from "@/lib/draft-form-preview";
import {
  liveApplyGapBanner,
  unfinishedDraftBanner,
} from "@/lib/draft-studio-banners";
import {
  formSlotCatalog,
  inheritHostModelFromDraft,
  inheritPlacementRows,
  isFieldPackDraft,
  primaryCustomModelFromDraft,
  refineSuggestionsFromDraft,
  viewDesignerHref,
} from "@/lib/draft-models";
import { operatorSurfaceFromDraft } from "@/lib/operator-surface";
import { odooMenuUrl, odooViewUrl, goldOptionAInspectLink } from "@/lib/odoo-urls";
import {
  studioAppIsLiveOnOdoo,
  studioApplyMenuTarget,
  studioPhaseFromSession,
  artifactMatchesLockedContract,
  type StudioSession,
} from "@/lib/studio-session";
import { studioJourneyFromPhase } from "@/lib/studio-journey";
import type { GoldHostStatus } from "./StudioOptionAPanel";

export function useStudioDerived(input: {
  connectionId: string;
  session: StudioSession | null;
  connection: Connection | null;
  goldHost: GoldHostStatus | null;
  goldValidationId: string | null;
  goldZipBase64: string | null;
  goldPromoted: boolean;
  odooAppUrl: string | null;
}) {
  const {
    connectionId,
    session,
    connection,
    goldHost,
    goldValidationId,
    goldZipBase64,
    goldPromoted,
    odooAppUrl,
  } = input;

  const draftOpts = useMemo(
    () => scaffoldOptsFromSpec(session?.artifact ?? null),
    [session?.artifact],
  );
  const canApply = scaffoldApplyAllowed(connection, draftOpts);
  const applyBlocked = scaffoldApplyBlockedReason(connection, draftOpts);
  const odooUrl = String((connection as { url?: string } | null | undefined)?.url || "");
  // Hosting is not always stored on the connection; an *.odoo.com address is Odoo Online.
  const isOdooOnline = connection?.hosting === "online" || isOdooOnlineUrl(odooUrl);

  const phase = useMemo(() => studioPhaseFromSession(session), [session]);
  const contractMatchesCanvas = artifactMatchesLockedContract(
    session?.artifact ?? null,
    session?.understanding ?? null,
  );
  const preview = useMemo(() => {
    if (!contractMatchesCanvas) return null;
    return residualFormPreviewFromDraft(session?.artifact ?? null);
  }, [session?.artifact, contractMatchesCanvas]);
  const stockReuse = isStockReuseDraft(session?.artifact ?? null);
  const refuseClone = isRefuseCloneDraft(session?.artifact ?? null);
  const goldOptionA = isGoldOptionADraft(session?.artifact ?? null);
  const authoredOptionA = isOptionAAuthoredDraft(session?.artifact ?? null);
  const authoringPassed = optionAAuthoringPassed(session?.artifact ?? null);
  const authoringRetryable = optionAAuthoringRetryable(session?.artifact ?? null);
  const authoringNeedsAutoRepair = optionAAuthoringNeedsAutoRepair(session?.artifact ?? null);
  const hostInstallOffers = useMemo(
    () => hostInstallOffersFromDraft(session?.artifact ?? null),
    [session?.artifact],
  );
  const leftoverAuthoringFindings = useMemo(
    () => authoringFindingsWithoutHostInstall(session?.artifact ?? null),
    [session?.artifact],
  );
  const goldHonesty = generationEngineFromDraft(session?.artifact ?? null)?.honesty || "";
  const goldSettings = optionASettingsFromDraft(session?.artifact ?? null);
  const goldId = generationEngineFromDraft(session?.artifact ?? null)?.gold_artifact_id || "";
  const goldInspect = useMemo(
    () =>
      goldOptionAInspectLink(goldId, connection?.url, {
        hostReady: goldHost?.host_ready,
        actionId: goldHost?.action_id,
        href: goldHost?.href,
      }),
    [goldId, connection?.url, goldHost],
  );
  const goldCanPromote = Boolean(goldValidationId && goldZipBase64) && !isOdooOnline;
  const goldNeedsInvoicing =
    goldOptionA && goldId === "currency_rate_cbn" && goldHost?.host_ready === false;
  const goldCanOpenSettings = Boolean(goldPromoted && goldInspect);
  const surfaceBlocked = surfaceGateBlocksInstall(session?.artifact ?? null);
  const surfaceFindings = useMemo(
    () => surfaceGateFindingsFromDraft(session?.artifact ?? null),
    [session?.artifact],
  );
  const grammarCard = useMemo(
    () => documentGrammarFromDraft(session?.artifact ?? null),
    [session?.artifact],
  );
  const stockApps = useMemo(
    () => stockAppsFromDraft(session?.artifact ?? null),
    [session?.artifact],
  );
  const applyTarget = useMemo(() => studioApplyMenuTarget(session), [session]);
  const fieldPack = isFieldPackDraft(session?.artifact ?? null);
  const inheritHost = inheritHostModelFromDraft(session?.artifact ?? null);
  const hostForOpen = applyTarget.hostModel || inheritHost;
  const fieldPackApplied = Boolean(applyTarget.applied && hostForOpen);
  const optionAHostLive =
    Boolean(goldPromoted && !goldOptionA && hostForOpen) ||
    (Boolean(applyTarget.applied && hostForOpen) && authoredOptionA);
  const appIsLiveOnOdoo =
    studioAppIsLiveOnOdoo(session) ||
    Boolean(odooAppUrl) ||
    fieldPackApplied ||
    goldPromoted ||
    optionAHostLive;
  const liveAppName = String(
    (session?.artifact?.display_name as string | undefined) ||
      preview?.title ||
      "this app",
  );
  const hostFormName = preview?.title || (fieldPack || authoredOptionA ? "this form" : liveAppName);
  const openInOdooUrl = useMemo(() => {
    const base = connection?.url?.replace(/\/$/, "") || "";
    if (!base) return odooAppUrl;
    // Option A / inherit host: never open a leftover menu_id (Discuss).
    const optionAHost =
      Boolean(goldPromoted && !goldOptionA && hostForOpen) ||
      (applyTarget.applied && Boolean(hostForOpen) && !applyTarget.rootMenuId);
    if (optionAHost && hostForOpen) {
      return odooViewUrl(base, hostForOpen, "list", applyTarget.openActionId);
    }
    if (applyTarget.rootMenuId) {
      return odooMenuUrl(base, applyTarget.rootMenuId, applyTarget.openActionId);
    }
    if (applyTarget.applied && hostForOpen) {
      return odooViewUrl(base, hostForOpen, "list", applyTarget.openActionId);
    }
    return odooAppUrl;
  }, [
    applyTarget,
    connection?.url,
    odooAppUrl,
    hostForOpen,
    goldPromoted,
    goldOptionA,
  ]);
  const refineChips = useMemo(
    () => refineSuggestionsFromDraft(session?.artifact ?? null),
    [session?.artifact],
  );
  const placementRows = useMemo(
    () => inheritPlacementRows(session?.artifact ?? null),
    [session?.artifact],
  );
  const slotCatalog = useMemo(
    () => formSlotCatalog(session?.artifact ?? null),
    [session?.artifact],
  );
  const designerHref = useMemo(() => {
    const fromDraft = viewDesignerHref(connectionId, session?.artifact ?? null);
    if (fromDraft.includes("?model=")) return fromDraft;
    const mid = String(preview?.model || inheritHost || "").trim();
    if (mid && !mid.endsWith("_line")) {
      return `/connections/${connectionId}/designer?model=${encodeURIComponent(mid)}`;
    }
    return fromDraft;
  }, [connectionId, session?.artifact, preview?.model, inheritHost]);
  const designerModel = useMemo(
    () =>
      primaryCustomModelFromDraft(session?.artifact ?? null) ||
      inheritHost ||
      (preview?.model && !preview.model.endsWith("_line") ? preview.model : null),
    [session?.artifact, inheritHost, preview?.model],
  );
  const clarification = session?.pending_clarification || session?.clarification || null;
  const operatorSurface = useMemo(
    () => operatorSurfaceFromDraft(session?.artifact ?? null),
    [session?.artifact],
  );
  const liveApplyBanner = useMemo(
    () => liveApplyGapBanner(session?.artifact ?? null, { surface: "studio" }),
    [session?.artifact],
  );
  const unfinishedBanner = useMemo(
    () => unfinishedDraftBanner(session?.artifact ?? null, { surface: "studio" }),
    [session?.artifact],
  );
  const journey = useMemo(
    () => studioJourneyFromPhase({ phase, applied: appIsLiveOnOdoo }),
    [phase, appIsLiveOnOdoo],
  );
  const appTitle = preview?.title || session?.prompt_resolved?.slice(0, 40) || "App draft";
  const canvas = phase === "review" || phase === "generating";
  const openLinkProps = {
    goldOptionA,
    goldCanOpenSettings,
    goldInspect,
    goldHostMessage: goldHost?.message,
    appIsLiveOnOdoo,
    openInOdooUrl,
    fieldPack: fieldPack || optionAHostLive,
    hostFormName,
    liveAppName,
  };
  const designerLinkProps = {
    href: designerHref,
    designerModel,
    appIsLiveOnOdoo,
    fieldPack,
    hostFormName,
  };

  return {
    draftOpts,
    canApply,
    applyBlocked,
    isOdooOnline,
    odooUrl,
    phase,
    contractMatchesCanvas,
    preview,
    stockReuse,
    refuseClone,
    goldOptionA,
    authoredOptionA,
    authoringPassed,
    authoringRetryable,
    authoringNeedsAutoRepair,
    hostInstallOffers,
    leftoverAuthoringFindings,
    goldHonesty,
    goldSettings,
    goldId,
    goldInspect,
    goldCanPromote,
    goldNeedsInvoicing,
    goldCanOpenSettings,
    surfaceBlocked,
    surfaceFindings,
    grammarCard,
    stockApps,
    applyTarget,
    fieldPack,
    inheritHost,
    hostForOpen,
    fieldPackApplied,
    optionAHostLive,
    appIsLiveOnOdoo,
    liveAppName,
    hostFormName,
    openInOdooUrl,
    refineChips,
    placementRows,
    slotCatalog,
    designerHref,
    designerModel,
    clarification,
    operatorSurface,
    liveApplyBanner,
    unfinishedBanner,
    journey,
    appTitle,
    canvas,
    openLinkProps,
    designerLinkProps,
  };
}

export type StudioDerived = ReturnType<typeof useStudioDerived>;
