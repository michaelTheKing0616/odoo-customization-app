"use client";

import { api } from "@/lib/api";
import { reportApiError } from "@/lib/api-error";
import type { OverlapFinding } from "./wizard-helpers";

type UseWizardConnectArgs = {
  connectionId: string;
  nlPrompt: string;
  grainOverride: string;
  connectPoints: Record<string, unknown> | null;
  selectedGalleryId: string;
  jsonPaste: string;
  setError: (value: string | null) => void;
  setAiNote: (value: string | null) => void;
  setAiDraft: (value: Record<string, unknown> | null) => void;
  setAiWarnings: (value: string[]) => void;
  setBusy: (value: boolean) => void;
  setAiBusyLabel: (value: string | null) => void;
  setOverlapBusy: (value: boolean) => void;
  setOverlapChoice: (value: string | null) => void;
  setOverlapFindingId: (value: string | null) => void;
  setOverlapFindings: (value: OverlapFinding[]) => void;
  setGrainOverride: (value: string) => void;
  setGrainLabel: (value: string | null) => void;
  setEffectiveGrain: (value: string) => void;
  setConnectPointsApproved: (value: boolean) => void;
  setConnectReviewBusy: (value: boolean) => void;
  setConnectPoints: (value: Record<string, unknown> | null) => void;
  setHostCandidates: (
    value: Array<{ model: string; label: string; score: number; reason?: string }>,
  ) => void;
  setSelectedGalleryId: (value: string) => void;
  setGenUiResult: (value: string | null) => void;
  setValidateLiveResult: (value: import("@/lib/api").ValidateLiveResult | null) => void;
  setJsonPasteOpen: (value: boolean) => void;
};

export function useWizardConnect({
  connectionId,
  nlPrompt,
  grainOverride,
  connectPoints,
  selectedGalleryId,
  jsonPaste,
  setError,
  setAiNote,
  setAiDraft,
  setAiWarnings,
  setBusy,
  setAiBusyLabel,
  setOverlapBusy,
  setOverlapChoice,
  setOverlapFindingId,
  setOverlapFindings,
  setGrainOverride,
  setGrainLabel,
  setEffectiveGrain,
  setConnectPointsApproved,
  setConnectReviewBusy,
  setConnectPoints,
  setHostCandidates,
  setSelectedGalleryId,
  setGenUiResult,
  setValidateLiveResult,
  setJsonPasteOpen,
}: UseWizardConnectArgs) {
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

  function onOverlapUse(finding: OverlapFinding) {
    setOverlapChoice("use");
    setOverlapFindingId(finding.id);
    if (finding.deep_link) {
      window.location.href = finding.deep_link;
    }
  }

  function onOverlapExtend(finding: OverlapFinding) {
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

  async function onLoadPastedJson(source: "paste" | "file", file?: File) {
    setError(null);
    setAiNote(null);
    let raw = jsonPaste.trim();
    if (source === "file" && file) {
      raw = await file.text();
    }
    if (!raw) {
      setError("Paste app-plan JSON or choose a .json file.");
      return;
    }
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      setError("That JSON is not an app plan. Paste an object with a models array.");
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
          "JSON loaded. Review it below, then Apply to Odoo (live prep and reuse wiring applied).",
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

  return {
    onCheckOverlap,
    onOverlapUse,
    onOverlapExtend,
    onOverlapBuildAnyway,
    onReviewConnectPoints,
    onLoadPastedJson,
  };
}
