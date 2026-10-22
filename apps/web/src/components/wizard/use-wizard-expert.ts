"use client";

import { api } from "@/lib/api";
import { reportApiError } from "@/lib/api-error";
import { expertShouldRepair } from "@/lib/draft-studio-banners";
import { confirmedReuseModelsFromDraft } from "@/lib/reuse-chips";

type UseWizardExpertArgs = {
  connectionId: string;
  nlPrompt: string;
  aiDraft: Record<string, unknown> | null;
  refreshDraftCacheList: () => Promise<void>;
  setNlPrompt: (value: string) => void;
  setReuseModels: (value: string[]) => void;
  setAiDraft: (value: Record<string, unknown> | null) => void;
  setAiBusy: (value: boolean) => void;
  setAiBusyLabel: (value: string | null) => void;
  setError: (value: string | null) => void;
  setAiNote: (value: string | null) => void;
  setOptionAProveBusy: (value: boolean) => void;
  setOptionAProveNote: (value: string | null) => void;
  setExpertReviewNote: (value: string | null) => void;
  setExpertReviewFindings: (
    value: import("@/lib/api").ExpertDraftReviewResponse["findings"],
  ) => void;
};

export function useWizardExpert({
  connectionId,
  nlPrompt,
  aiDraft,
  refreshDraftCacheList,
  setNlPrompt,
  setReuseModels,
  setAiDraft,
  setAiBusy,
  setAiBusyLabel,
  setError,
  setAiNote,
  setOptionAProveBusy,
  setOptionAProveNote,
  setExpertReviewNote,
  setExpertReviewFindings,
}: UseWizardExpertArgs) {
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
          ? `Restored saved snapshot: ${row.summary}. This is not Expert review. Use “Ask the Expert to review and fix” only if JSON findings remain.`
          : `Restored saved snapshot: ${row.summary}. No JSON gaps to repair, so the Expert will leave this spec unchanged.`,
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
    setAiBusyLabel("Sandbox install and custom-code smoke test…");
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
          `Sandbox smoke passed. Score ${score}/10. go_live_ready=${Boolean(res.go_live_ready)}. Publishing stays a step you confirm.`,
        );
      } else {
        const msg =
          (res.sandbox as { message?: string } | undefined)?.message ||
          (res.smoke as { message?: string } | undefined)?.message ||
          "Sandbox smoke failed";
        setOptionAProveNote(`${msg} (score capped until smoke passes)`);
      }
    } catch (err) {
      reportApiError(err, setError, { fallback: "Custom-code test-copy check failed" });
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

  return { restoreDraftFromCache, proveOptionASandbox, askExpertReviewDraft };
}
