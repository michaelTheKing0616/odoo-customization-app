"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { api, ClarificationRequiredError } from "@/lib/api";
import {
  rememberStudioSession,
  sessionWithClarification,
  type StudioUnderstanding,
} from "@/lib/studio-session";
import type { StudioState } from "./use-studio-state";
import { effectiveAiStep } from "./brief-wants-ai";

export function useStudioBrief(
  connectionId: string,
  s: Pick<
    StudioState,
    | "session"
    | "prompt"
    | "flashAstEnrich"
    | "setError"
    | "setBusy"
    | "setSession"
  >,
  startOver: () => void,
) {
  const router = useRouter();
  const { session, prompt, flashAstEnrich, setError, setBusy, setSession } = s;

  async function startSession() {
    if (!connectionId?.trim()) {
      setError("Open App Studio from a connection page, then try again.");
      return;
    }
    setError(null);
    setBusy("create");
    try {
      const created = await api.createStudioSession({
        connection_id: connectionId.trim(),
        prompt: prompt.trim() || String(session?.prompt_original || "").trim(),
        flash_ast_enrich: effectiveAiStep(flashAstEnrich, prompt),
      });
      setSession(created);
      rememberStudioSession(connectionId, created.id);
      if (created.pending_clarification || created.clarification) {
        router.replace(`/connections/${connectionId}/studio?session=${created.id}`);
        return;
      }
      if (created.status === "ready") {
        setBusy("generate");
        try {
          const gen = await api.generateStudioSession(created.id);
          setSession(gen);
          router.replace(`/connections/${connectionId}/studio?session=${gen.id}`);
        } catch (genErr) {
          if (genErr instanceof ClarificationRequiredError) {
            setSession(sessionWithClarification(created, genErr.clarification));
            router.replace(`/connections/${connectionId}/studio?session=${created.id}`);
            return;
          }
          throw genErr;
        }
      } else {
        router.replace(`/connections/${connectionId}/studio?session=${created.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start session");
    } finally {
      setBusy(null);
    }
  }

  async function submitClarify(
    mergeKey: string,
    answerId: string,
    answerText?: string,
    understanding?: StudioUnderstanding,
  ) {
    if (!session) return;
    setError(null);
    setBusy("clarify");
    try {
      const updated = await api.clarifyStudioSession(session.id, {
        merge_key: mergeKey,
        answer_id: answerId,
        answer_text: answerText || "",
        understanding,
      });
      setSession(updated);
      if (updated.status === "rejected" || updated.rejected) {
        startOver();
        return;
      }
      if (!updated.pending_clarification && updated.status === "ready") {
        try {
          const gen = await api.generateStudioSession(updated.id);
          setSession(gen);
        } catch (genErr) {
          if (genErr instanceof ClarificationRequiredError) {
            setSession(sessionWithClarification(updated, genErr.clarification));
            return;
          }
          throw genErr;
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Clarification failed");
    } finally {
      setBusy(null);
    }
  }

  /** GND-MOD: answer the stock-app install step. Throws a one-sentence Error on install failure. */
  async function resolveStockApp(decision: "install" | "decline") {
    if (!session) return;
    setError(null);
    const updated = await api.decideStudioStockApp(session.id, decision);
    if (updated.stopped) {
      toast(updated.message || "Stopped. This request was not built.");
      startOver();
      return;
    }
    setSession(updated);
    if (!updated.pending_clarification && updated.status === "ready") {
      try {
        const gen = await api.generateStudioSession(updated.id);
        setSession(gen);
      } catch (genErr) {
        if (genErr instanceof ClarificationRequiredError) {
          setSession(sessionWithClarification(updated, genErr.clarification));
          return;
        }
        setError(genErr instanceof Error ? genErr.message : "Generation failed");
      }
    }
  }

  /** S11: install the apps the design is built on, then show the re-checked diagnosis. */
  async function installApps() {
    if (!session) return;
    setError(null);
    const updated = await api.installStudioApps(session.id);
    const errors = updated.install_errors ?? [];
    setSession(updated);
    if (errors.length) throw new Error(errors[0]);
  }

  return { startSession, submitClarify, resolveStockApp, installApps };
}
