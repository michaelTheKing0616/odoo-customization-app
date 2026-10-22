"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef } from "react";
import { api, ClarificationRequiredError, type JobRow } from "@/lib/api";
import { JobPollError, pollJob } from "@/lib/jobs";
import {
  forgetStudioSession,
  loadRememberedStudioSession,
  loadStashedStudioPrompt,
  rememberStudioSession,
  sessionWithClarification,
  type StudioSession,
} from "@/lib/studio-session";
import { draftFromJobResult } from "@/lib/studio-journey";
import { POLL_ATTEMPTS, POLL_MS } from "./studio-constants";
import type { StudioState } from "./use-studio-state";
import type { StudioDerived } from "./use-studio-derived";

export function useStudioSession(
  connectionId: string,
  s: StudioState,
  d: Pick<StudioDerived, "phase" | "authoringNeedsAutoRepair">,
) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionIdParam = searchParams.get("session");
  const {
    session,
    busy,
    setSession,
    setJob,
    setError,
    setErrorStep,
    setBusy,
    setRefineInput,
    setLocalRefineError,
    setHighlightIds,
    setFlashId,
    setOdooAppUrl,
    setApplyNote,
    setCalloutTitle,
    setGoldValidationId,
    setGoldZipBase64,
    setGoldPromoted,
    setLastSandboxFault,
    setGoldHost,
    setInstallOpen,
    setPromoteOpen,
    setConnection,
    setPrompt,
    setFlashAstEnrich,
    setFlashAstEnrichHelp,
    beginStudioAction,
    failStudio,
  } = s;
  const { phase, authoringNeedsAutoRepair } = d;

  const loadSession = useCallback(async (id: string) => {
    const row = await api.getStudioSession(id);
    setSession(row);
    return row;
  }, [setSession]);

  const startOver = useCallback(() => {
    forgetStudioSession(connectionId);
    setSession(null);
    setJob(null);
    setError(null);
    setErrorStep(null);
    setBusy(null);
    setRefineInput("");
    setLocalRefineError(null);
    setHighlightIds([]);
    setFlashId(null);
    setOdooAppUrl(null);
    setApplyNote(null);
    setCalloutTitle("Applied to Odoo");
    setGoldValidationId(null);
    setGoldZipBase64(null);
    setGoldPromoted(false);
    setLastSandboxFault(null);
    setGoldHost(null);
    setInstallOpen(false);
    setPromoteOpen(false);
    router.replace(`/connections/${connectionId}/studio`);
  }, [
    connectionId,
    router,
    setSession,
    setJob,
    setError,
    setErrorStep,
    setBusy,
    setRefineInput,
    setLocalRefineError,
    setHighlightIds,
    setFlashId,
    setOdooAppUrl,
    setApplyNote,
    setCalloutTitle,
    setGoldValidationId,
    setGoldZipBase64,
    setGoldPromoted,
    setLastSandboxFault,
    setGoldHost,
    setInstallOpen,
    setPromoteOpen,
  ]);

  const retryGeneration = useCallback(async () => {
    if (!session) return;
    beginStudioAction();
    setBusy("generate");
    try {
      const gen = await api.generateStudioSession(session.id);
      setSession(gen);
      setJob(null);
      router.replace(`/connections/${connectionId}/studio?session=${gen.id}`);
    } catch (err) {
      if (err instanceof ClarificationRequiredError) {
        setSession(sessionWithClarification(session, err.clarification));
        return;
      }
      failStudio("generate", err instanceof Error ? err.message : "Generation failed");
    } finally {
      setBusy(null);
    }
  }, [
    connectionId,
    router,
    session,
    beginStudioAction,
    setBusy,
    setSession,
    setJob,
    failStudio,
  ]);

  const jsonAutoRepairKey = session?.id ? `studio-auto-json-repair:${session.id}` : "";
  const jsonAutoRepairStarted = useRef<string | null>(null);

  useEffect(() => {
    if (phase !== "review" || !session?.id || busy || !authoringNeedsAutoRepair) return;
    const key = jsonAutoRepairKey;
    if (!key || jsonAutoRepairStarted.current === key) return;
    try {
      if (sessionStorage.getItem(key)) return;
      sessionStorage.setItem(key, "1");
    } catch {
      /* private mode — still one in-memory shot */
    }
    jsonAutoRepairStarted.current = key;
    void retryGeneration();
  }, [authoringNeedsAutoRepair, busy, jsonAutoRepairKey, phase, retryGeneration, session?.id]);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch(() => setConnection(null));
  }, [connectionId, setConnection]);

  useEffect(() => {
    const stashed = loadStashedStudioPrompt(connectionId);
    if (stashed) setPrompt(stashed);
  }, [connectionId, setPrompt]);

  useEffect(() => {
    const sessionId = sessionIdParam || loadRememberedStudioSession(connectionId);
    if (!sessionId) {
      setSession(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        let row = await loadSession(sessionId);
        if (cancelled) return;

        if (row.status === "ready" && !row.job_id) {
          try {
            const gen = await api.generateStudioSession(row.id);
            if (cancelled) return;
            setSession(gen);
            router.replace(`/connections/${connectionId}/studio?session=${gen.id}`);
            return;
          } catch (genErr) {
            if (cancelled) return;
            if (genErr instanceof ClarificationRequiredError) {
              setSession(sessionWithClarification(row, genErr.clarification));
              return;
            }
            throw genErr;
          }
        }

        if (row.job_id && (row.status === "generating" || row.status === "failed")) {
          try {
            const terminalJob = await api.getJob(row.job_id);
            if (!cancelled) setJob(terminalJob);
            if (terminalJob.status === "failed" || terminalJob.status === "succeeded") {
              row = await api.syncStudioJob(row.id);
              if (!cancelled) setSession(row);
            }
          } catch {
            /* job lookup optional */
          }
        }

        if (!sessionIdParam && row.status === "failed") {
          forgetStudioSession(connectionId);
          if (!cancelled) {
            setSession(null);
            setJob(null);
          }
        }
      } catch (err) {
        if (cancelled) return;
        forgetStudioSession(connectionId);
        setSession(null);
        setError(err instanceof Error ? err.message : "Failed to load session");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [connectionId, sessionIdParam, loadSession, router, setSession, setJob, setError]);

  useEffect(() => {
    if (!session?.job_id || phase !== "generating") return;
    const sessionId = session.id;
    const jobId = session.job_id;
    const sessionSnapshot = session;
    let cancelled = false;

    const markFailed = (message: string, jobRow?: JobRow | null) => {
      if (jobRow) setJob(jobRow);
      setError(message);
      setSession((cur) => (cur ? { ...cur, status: "failed" } : cur));
    };

    const enterReview = (synced: StudioSession) => {
      setSession(synced);
      setError(null);
      rememberStudioSession(connectionId, synced.id);
      router.replace(`/connections/${connectionId}/studio?session=${synced.id}&phase=review`);
    };

    (async () => {
      try {
        const terminal = await pollJob(jobId, {
          intervalMs: POLL_MS,
          maxAttempts: POLL_ATTEMPTS,
          untilTerminal: true,
          fetchJob: api.getJob,
          onUpdate: (j) => {
            if (!cancelled) setJob(j);
          },
        });
        if (cancelled) return;
        setJob(terminal);

        if (terminal.status !== "succeeded") {
          try {
            const synced = await api.syncStudioJob(sessionId);
            if (!cancelled) setSession({ ...synced, status: "failed" });
          } catch {
            if (!cancelled) markFailed(terminal.error || "Generation failed", terminal);
            return;
          }
          if (!cancelled) setError(terminal.error || "Generation failed");
          return;
        }

        try {
          const synced = await api.syncStudioJob(sessionId);
          if (cancelled) return;
          if (synced.status === "failed") {
            markFailed(
              (synced as StudioSession & { job_error?: string }).job_error ||
                "Generation finished without a usable draft",
              terminal,
            );
            return;
          }
          enterReview(synced);
        } catch (syncErr) {
          if (cancelled) return;
          const draft = draftFromJobResult(terminal);
          if (draft) {
            enterReview({
              ...sessionSnapshot,
              status: "review",
              artifact: draft,
            });
            return;
          }
          markFailed(
            syncErr instanceof Error ? syncErr.message : "Could not load the finished draft",
            terminal,
          );
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof JobPollError) {
          markFailed(err.message, err.job);
        } else {
          markFailed(err instanceof Error ? err.message : "Generation failed");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [session?.id, session?.job_id, phase, connectionId, router]);

  useEffect(() => {
    if (!connectionId?.trim()) return;
    let cancelled = false;
    (async () => {
      try {
        const prefs = await api.getStudioPrefs(connectionId.trim());
        if (cancelled) return;
        // null = follow env → default UI off (honest: no Flash unless operator asks)
        setFlashAstEnrich(typeof prefs.flash_ast_enrich === "boolean" ? prefs.flash_ast_enrich : null);
        if (prefs.flash_ast_enrich_help) setFlashAstEnrichHelp(prefs.flash_ast_enrich_help);
      } catch {
        /* prefs are optional — keep product default off */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [connectionId, setFlashAstEnrich, setFlashAstEnrichHelp]);

  return { startOver, retryGeneration };
}
