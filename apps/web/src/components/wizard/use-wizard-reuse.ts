"use client";

import { api } from "@/lib/api";
import { reportApiError, isApiNotFound } from "@/lib/api-error";
import type { HostInstallOffer } from "@/lib/draft-form-preview";
import { CONFIRM_PHRASE } from "./wizard-helpers";

type UseWizardReuseArgs = {
  connectionId: string;
  nlPrompt: string;
  aiDraft: Record<string, unknown> | null;
  reuseModels: string[];
  rejectedInferredReuse: string[];
  reloadReuseCatalog: () => Promise<void>;
  onDraftFromPrompt: (opts?: {
    reuseOverride?: string[];
    rejectedOverride?: string[];
    busyLabel?: string;
  }) => Promise<void>;
  setReuseModels: (
    value: string[] | ((prev: string[]) => string[]),
  ) => void;
  setRejectedInferredReuse: (value: string[]) => void;
  setAiBusy: (value: boolean) => void;
  setAiBusyLabel: (value: string | null) => void;
  setError: (value: string | null) => void;
  setAiDraft: (value: Record<string, unknown> | null) => void;
  setAiWarnings: (
    value: string[] | ((prev: string[]) => string[]),
  ) => void;
  setAiNote: (value: string | null) => void;
};

export function useWizardReuse({
  connectionId,
  nlPrompt,
  aiDraft,
  reuseModels,
  rejectedInferredReuse,
  reloadReuseCatalog,
  onDraftFromPrompt,
  setReuseModels,
  setRejectedInferredReuse,
  setAiBusy,
  setAiBusyLabel,
  setError,
  setAiDraft,
  setAiWarnings,
  setAiNote,
}: UseWizardReuseArgs) {
  // Do NOT sync reuse.plan.models or auto-confirmed connection decisions into chips.
  // Those lists include suggestions. Merging them into operator chips makes the next
  // Confirm/Install reapply treat every sibling as operator_reuse — Suggested and
  // Installable rows vanish. Snapshot restore uses confirmedReuseModelsFromDraft.

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

  return {
    reapplyReuseToDraft,
    confirmInferredReuse,
    rejectInferredReuse,
    confirmInstallableReuse,
    installAuthoredHostModule,
    rejectInstallableReuse,
    toggleReuse,
  };
}
