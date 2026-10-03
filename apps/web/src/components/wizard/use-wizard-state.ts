"use client";

import { useState } from "react";
import {
  type AppTemplate,
  type Connection,
  type ExpertDraftReviewResponse,
  type ProtectedModuleRefusal,
  type ScaffoldResult,
  type ReuseModelRow,
  type ValidateLiveResult,
} from "@/lib/api";
import {
  type DraftCacheEntry,
  type GalleryItem,
  type HostCandidate,
  type OverlapFinding,
} from "./wizard-helpers";

export function useWizardState() {
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
  const [zipBusy, setZipBusy] = useState(false);
  const [optionAProveBusy, setOptionAProveBusy] = useState(false);
  const [optionAProveNote, setOptionAProveNote] = useState<string | null>(null);
  const [expertReviewNote, setExpertReviewNote] = useState<string | null>(null);
  const [expertReviewFindings, setExpertReviewFindings] = useState<
    ExpertDraftReviewResponse["findings"]
  >([]);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiBusyLabel, setAiBusyLabel] = useState<string | null>(null);
  const [aiRefusals, setAiRefusals] = useState<ProtectedModuleRefusal[]>([]);
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
  const [draftCacheEntries, setDraftCacheEntries] = useState<DraftCacheEntry[]>([]);
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
  const [validateLiveResult, setValidateLiveResult] = useState<ValidateLiveResult | null>(
    null,
  );
  const [skipValidateLive, setSkipValidateLive] = useState(false);
  const [grainLabel, setGrainLabel] = useState<string | null>(null);
  const [grainOverride, setGrainOverride] = useState<string>("");
  const [connectPoints, setConnectPoints] = useState<Record<string, unknown> | null>(null);
  const [hostCandidates, setHostCandidates] = useState<HostCandidate[]>([]);
  const [componentGallery, setComponentGallery] = useState<GalleryItem[]>([]);
  const [selectedGalleryId, setSelectedGalleryId] = useState("");
  const [connectPointsApproved, setConnectPointsApproved] = useState(false);
  const [connectReviewBusy, setConnectReviewBusy] = useState(false);
  const [effectiveGrain, setEffectiveGrain] = useState<string>("");
  const [overlapFindings, setOverlapFindings] = useState<OverlapFinding[]>([]);
  const [overlapChoice, setOverlapChoice] = useState<string | null>(null);
  const [overlapFindingId, setOverlapFindingId] = useState<string | null>(null);
  const [overlapBusy, setOverlapBusy] = useState(false);

  return {
    connection,
    setConnection,
    templates,
    setTemplates,
    selected,
    setSelected,
    displayName,
    setDisplayName,
    technicalPrefix,
    setTechnicalPrefix,
    multiCompany,
    setMultiCompany,
    confirmOpen,
    setConfirmOpen,
    busy,
    setBusy,
    loading,
    setLoading,
    error,
    setError,
    result,
    setResult,
    nlPrompt,
    setNlPrompt,
    aiDraft,
    setAiDraft,
    aiNote,
    setAiNote,
    aiWarnings,
    setAiWarnings,
    zipBusy,
    setZipBusy,
    optionAProveBusy,
    setOptionAProveBusy,
    optionAProveNote,
    setOptionAProveNote,
    expertReviewNote,
    setExpertReviewNote,
    expertReviewFindings,
    setExpertReviewFindings,
    aiBusy,
    setAiBusy,
    aiBusyLabel,
    setAiBusyLabel,
    aiRefusals,
    setAiRefusals,
    aiEnabled,
    setAiEnabled,
    aiProviderLabel,
    setAiProviderLabel,
    ollamaDetail,
    setOllamaDetail,
    reuseModels,
    setReuseModels,
    rejectedInferredReuse,
    setRejectedInferredReuse,
    reuseCatalog,
    setReuseCatalog,
    reuseSearch,
    setReuseSearch,
    reuseCatalogStatus,
    setReuseCatalogStatus,
    reuseCatalogError,
    setReuseCatalogError,
    jsonPaste,
    setJsonPaste,
    jsonPasteOpen,
    setJsonPasteOpen,
    draftCacheEntries,
    setDraftCacheEntries,
    genUiConfirmOpen,
    setGenUiConfirmOpen,
    eliteBusy,
    setEliteBusy,
    eliteNote,
    setEliteNote,
    eliteValidationId,
    setEliteValidationId,
    eliteZipBase64,
    setEliteZipBase64,
    elitePromoteConfirmOpen,
    setElitePromoteConfirmOpen,
    eliteLintOk,
    setEliteLintOk,
    eliteLintNote,
    setEliteLintNote,
    genUiResult,
    setGenUiResult,
    odooAppUrl,
    setOdooAppUrl,
    walkthroughConfirmOpen,
    setWalkthroughConfirmOpen,
    validateLiveResult,
    setValidateLiveResult,
    skipValidateLive,
    setSkipValidateLive,
    grainLabel,
    setGrainLabel,
    grainOverride,
    setGrainOverride,
    connectPoints,
    setConnectPoints,
    hostCandidates,
    setHostCandidates,
    componentGallery,
    setComponentGallery,
    selectedGalleryId,
    setSelectedGalleryId,
    connectPointsApproved,
    setConnectPointsApproved,
    connectReviewBusy,
    setConnectReviewBusy,
    effectiveGrain,
    setEffectiveGrain,
    overlapFindings,
    setOverlapFindings,
    overlapChoice,
    setOverlapChoice,
    overlapFindingId,
    setOverlapFindingId,
    overlapBusy,
    setOverlapBusy,
  };
}

export type WizardState = ReturnType<typeof useWizardState>;
