"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChatBubble } from "@/components/studio/ChatBubble";
import { ClarifyInterstitial } from "@/components/studio/ClarifyInterstitial";
import { HostInstallPanel } from "@/components/studio/HostInstallDialog";
import { ModelTierBadge } from "@/components/studio/ModelTierBadge";
import { RefineHistoryPopover } from "@/components/studio/RefineHistoryPopover";
import { ReviewRefineLayout } from "@/components/studio/ReviewRefineLayout";
import { DraftOdooPreview } from "@/components/odoo-preview";
import { Spokes } from "@/components/loading-ui/spokes";
import { StudioBusyLabel } from "@/components/studio/StudioBusyLabel";
import { StudioProgress } from "@/components/studio/StudioProgress";
import { SuggestionChip } from "@/components/studio/SuggestionChip";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { api, ClarificationRequiredError, ConfirmationRequiredError, Connection, JobRow } from "@/lib/api";
import { reportApiError, isApiNotFound } from "@/lib/api-error";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
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
  type HostInstallOffer,
  optionASettingsFromDraft,
  residualFormPreviewFromDraft,
  stockAppsFromDraft,
  surfaceGateBlocksInstall,
  surfaceGateFindingsFromDraft,
} from "@/lib/draft-form-preview";
import {
  formSlotCatalog,
  inheritHostModelFromDraft,
  inheritPlacementRows,
  isFieldPackDraft,
  primaryCustomModelFromDraft,
  refineSuggestionsFromDraft,
  viewDesignerHref,
} from "@/lib/draft-models";
import { odooMenuUrl, odooViewUrl, goldOptionAInspectLink } from "@/lib/odoo-urls";
import { JobPollError, pollJob } from "@/lib/jobs";
import {
  forgetStudioSession,
  loadRememberedStudioSession,
  loadStashedStudioPrompt,
  rememberStudioSession,
  STUDIO_STARTER_CHIPS,
  studioAppIsLiveOnOdoo,
  studioApplyMenuTarget,
  sessionWithClarification,
  studioPhaseFromSession,
  undoInstructionForRefine,
  type StudioSession,
} from "@/lib/studio-session";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import "@/styles/studio-refinement.css";

const POLL_MS = 2500;
const POLL_ATTEMPTS = 900;
const CONFIRM_PHRASE = "I understand the risks";

function sandboxInstallFailed(draft: Record<string, unknown> | null | undefined): boolean {
  const row = draft?._sandbox_install;
  return Boolean(row && typeof row === "object" && (row as { ok?: boolean }).ok === false);
}

function feedbackRepairFromDraft(draft: Record<string, unknown> | null | undefined): {
  applied?: boolean;
  message?: string;
} | null {
  const row = draft?._option_a_feedback_repair;
  if (!row || typeof row !== "object") return null;
  return row as { applied?: boolean; message?: string };
}

function displayFault(text: string, max = 1600): string {
  const trimmed = text.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max)}…`;
}

const CHIP_LABELS: Record<string, string> = {
  "Car rental with deposits and return checklist": "Car rental",
  "Clinic booking with walk-in appointments": "Clinic booking",
  "Helpdesk tickets with requester and status workflow": "Helpdesk tickets",
  "Retail inventory and stock moves": "Retail inventory",
};

function progressLabelFromJob(job: JobRow | null): string {
  const result = (job?.result ?? {}) as Record<string, unknown>;
  const step =
    (typeof result.step_label === "string" && result.step_label) ||
    (typeof result.progress_label === "string" && result.progress_label) ||
    null;
  if (step) {
    return step.replace(/^Stage [A-Z]\s*·?\s*/i, "").trim() || "Building your draft…";
  }
  if (job?.status === "queued") return "Queued…";
  if (job?.status === "running") return "Building your draft…";
  return "Building your draft…";
}

function draftFromJobResult(job: JobRow | null): Record<string, unknown> | null {
  const draft = job?.result?.draft;
  if (draft && typeof draft === "object" && !Array.isArray(draft)) {
    return draft as Record<string, unknown>;
  }
  return null;
}

export default function AppStudioPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const connectionId = params.id;
  useSyncShellContext({ route: "app-studio" });

  const sessionIdParam = searchParams.get("session");
  const [prompt, setPrompt] = useState("");
  const [session, setSession] = useState<StudioSession | null>(null);
  const [job, setJob] = useState<JobRow | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refineInput, setRefineInput] = useState("");
  const [localRefineError, setLocalRefineError] = useState<string | null>(null);
  const [highlightIds, setHighlightIds] = useState<string[]>([]);
  const [flashId, setFlashId] = useState<string | null>(null);
  const [connection, setConnection] = useState<Connection | null>(null);
  const [applyOpen, setApplyOpen] = useState(false);
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [repairNotes, setRepairNotes] = useState("");
  const [applyNote, setApplyNote] = useState<string | null>(null);
  const [calloutTitle, setCalloutTitle] = useState("Applied to Odoo");
  const [odooAppUrl, setOdooAppUrl] = useState<string | null>(null);
  const [goldValidationId, setGoldValidationId] = useState<string | null>(null);
  const [goldZipBase64, setGoldZipBase64] = useState<string | null>(null);
  const [goldPromoted, setGoldPromoted] = useState(false);
  const [goldHost, setGoldHost] = useState<{
    host_ready: boolean;
    missing_depends: string[];
    install_module?: string | null;
    install_label?: string | null;
    href?: string | null;
    label?: string;
    message?: string;
    action_id?: number | null;
  } | null>(null);
  const [installOpen, setInstallOpen] = useState(false);
  const [mobileTab, setMobileTab] = useState<"preview" | "chat">("preview");

  const draftOpts = useMemo(
    () => scaffoldOptsFromSpec(session?.artifact ?? null),
    [session?.artifact],
  );
  const canApply = scaffoldApplyAllowed(connection, draftOpts);
  const applyBlocked = scaffoldApplyBlockedReason(connection, draftOpts);
  const isOdooOnline = connection?.hosting === "online";

  const phase = useMemo(() => studioPhaseFromSession(session), [session]);
  const preview = useMemo(
    () => residualFormPreviewFromDraft(session?.artifact ?? null),
    [session?.artifact],
  );
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
  const authoredSandboxFailed = authoredOptionA && sandboxInstallFailed(session?.artifact);
  const lastFeedbackRepair = feedbackRepairFromDraft(session?.artifact);
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
  const appIsLiveOnOdoo =
    studioAppIsLiveOnOdoo(session) || Boolean(odooAppUrl) || fieldPackApplied;
  const liveAppName = String(
    (session?.artifact?.display_name as string | undefined) ||
      preview?.title ||
      "this app",
  );
  const hostFormName = preview?.title || (fieldPack ? "this form" : liveAppName);
  const openInOdooUrl = useMemo(() => {
    const base = connection?.url?.replace(/\/$/, "") || "";
    if (!base) return odooAppUrl;
    if (applyTarget.rootMenuId) {
      return odooMenuUrl(base, applyTarget.rootMenuId, applyTarget.openActionId);
    }
    if (applyTarget.applied && hostForOpen) {
      return odooViewUrl(base, hostForOpen, "list", applyTarget.openActionId);
    }
    return odooAppUrl;
  }, [applyTarget, connection?.url, odooAppUrl, hostForOpen]);
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

  const loadSession = useCallback(async (id: string) => {
    const row = await api.getStudioSession(id);
    setSession(row);
    return row;
  }, []);

  const startOver = useCallback(() => {
    forgetStudioSession(connectionId);
    setSession(null);
    setJob(null);
    setError(null);
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
    setGoldHost(null);
    setInstallOpen(false);
    setPromoteOpen(false);
    setRepairNotes("");
    router.replace(`/connections/${connectionId}/studio`);
  }, [connectionId, router]);

  const retryGeneration = useCallback(async () => {
    if (!session) return;
    setError(null);
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
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setBusy(null);
    }
  }, [connectionId, router, session]);

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
  }, [connectionId]);

  useEffect(() => {
    if (!goldOptionA || !goldId) {
      setGoldHost(null);
      return;
    }
    let cancelled = false;
    api
      .goldInspect(connectionId, goldId)
      .then((row) => {
        if (!cancelled) setGoldHost(row);
      })
      .catch(() => {
        if (!cancelled) setGoldHost(null);
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, goldOptionA, goldId, goldPromoted]);

  useEffect(() => {
    const stashed = loadStashedStudioPrompt(connectionId);
    if (stashed) setPrompt(stashed);
  }, [connectionId]);

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
  }, [connectionId, sessionIdParam, loadSession, router]);

  useEffect(() => {
    if (!session?.job_id || phase !== "generating") return;
    const sessionId = session.id;
    const jobId = session.job_id;
    const sessionSnapshot = session;
    let cancelled = false;

    const markFailed = (message: string, jobRow?: JobRow | null) => {
      if (jobRow) setJob(jobRow);
      setError(message);
      setSession((s) => (s ? { ...s, status: "failed" } : s));
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
          // Never leave the user on a spinner after a finished job.
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

  async function startSession() {
    setError(null);
    setBusy("create");
    try {
      const created = await api.createStudioSession({
        connection_id: connectionId,
        prompt: prompt.trim(),
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
    understanding?: import("@/lib/studio-session").StudioUnderstanding,
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

  async function submitRefine(instruction?: string) {
    const text = (instruction ?? refineInput).trim();
    if (!session || text.length < 3) return;
    setError(null);
    setLocalRefineError(null);
    setBusy("refine");
    try {
      const out = await api.refineStudioSession(session.id, text);
      if (out.needs_clarification) {
        setSession(out.session);
        return;
      }
      setSession(out.session);
      if (!instruction) setRefineInput("");
      if (!out.ok) {
        setLocalRefineError(out.error || "Could not apply that change.");
        return;
      }
      const ids = out.highlighted_field_ids || [];
      setHighlightIds(ids);
      if (ids[0]) {
        setFlashId(ids[0]);
        window.setTimeout(() => setFlashId(null), 2400);
      }
      setMobileTab("preview");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Refinement failed";
      if (/could not (map|apply)/i.test(message)) {
        setLocalRefineError(message);
        if (!instruction) setRefineInput("");
        return;
      }
      setError(message);
    } finally {
      setBusy(null);
    }
  }

  function downloadZipBase64(tech: string, zipBase64: string) {
    const bin = atob(zipBase64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const blob = new Blob([bytes], { type: "application/zip" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${tech || "module"}.zip`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function downloadGoldZip() {
    const spec = session?.artifact;
    if (!spec) return;
    setError(null);
    setBusy("zip");
    try {
      const res = await api.exportModuleSpecZip(connectionId, { spec });
      if (!res.zip_base64) {
        setError("Zip export returned no file.");
        return;
      }
      downloadZipBase64(String(res.module || spec.technical_name || "currency_rate_cbn"), res.zip_base64);
      setCalloutTitle("Module zip downloaded");
      setApplyNote(
        "Downloaded the Option A zip. Next: Sandbox install & smoke (proof only), then Promote onto this connection. Open Accounting Settings is this Odoo — not the ephemeral sandbox.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Zip export failed");
    } finally {
      setBusy(null);
    }
  }

  async function proveGoldSandbox() {
    const spec = session?.artifact;
    if (!spec) return;
    setError(null);
    setBusy("prove");
    try {
      const res = await api.proveOptionA(connectionId, { spec });
      if (res.draft) {
        setSession((s) => (s ? { ...s, artifact: res.draft as Record<string, unknown> } : s));
      }
      if (res.ok) {
        if (res.validation_id && res.zip_base64) {
          setGoldValidationId(res.validation_id);
          setGoldZipBase64(res.zip_base64);
          setGoldPromoted(false);
        }
        setCalloutTitle(
          res.feedback_repair?.applied ? "Sandbox proved after AI repair" : "Sandbox proved",
        );
        setApplyNote(
          res.message ||
            (res.promote_ready
              ? "Ephemeral sandbox passed and was torn down. Promote installs the zip on THIS connection. Then open Accounting Settings (not App Studio Open in Odoo)."
              : "Sandbox install passed. Promote stays human — this connection’s Odoo is where you inspect CBN, not :18069."),
        );
      } else {
        const msg =
          res.message ||
          (res.sandbox as { message?: string } | undefined)?.message ||
          (res.smoke as { message?: string } | undefined)?.message ||
          "Sandbox prove failed";
        setError(msg);
        if (res.feedback_repair?.applied) {
          setCalloutTitle("AI patched the module");
          setApplyNote(
            res.feedback_repair.message ||
              "The model patched files from the sandbox Fault. Retry Sandbox install & smoke, or Repair with AI. Do not click Install this app.",
          );
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sandbox prove failed");
    } finally {
      setBusy(null);
    }
  }

  async function promoteGoldModule(phrase: string) {
    const spec = session?.artifact;
    if (!spec || !goldValidationId || !goldZipBase64) return;
    setError(null);
    setBusy("promote");
    try {
      const tech = String(spec.technical_name || goldId || "custom_module");
      const res = await api.promoteModule(connectionId, {
        technical_name: tech,
        display_name: String(spec.display_name || tech),
        zip_base64: goldZipBase64,
        validation_id: goldValidationId,
        install_mode: "python",
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setPromoteOpen(false);
      setGoldPromoted(true);
      setCalloutTitle("Promoted to this connection");
      try {
        const row = await api.goldInspect(connectionId, goldId);
        setGoldHost(row);
      } catch {
        /* inspect is best-effort after promote */
      }
      setApplyNote(
        res.message ||
          `Promoted ${tech} onto this connection. Open Invoicing → Configuration → Settings (not Settings → Currency). Service = Central Bank of Nigeria → Update now → Currencies → USD → Rates.`,
      );
    } catch (err) {
      reportApiError(err, setError, { fallback: "Promote failed", toast: true });
    } finally {
      setBusy(null);
    }
  }

  async function installGoldHostModule(phrase: string) {
    const moduleName = goldHost?.install_module;
    if (!moduleName || phrase !== CONFIRM_PHRASE) return;
    setError(null);
    setBusy("install-host");
    try {
      const res = await api.installCommunityModule(connectionId, moduleName);
      setInstallOpen(false);
      if (!res.ok) {
        setError(res.message || `Could not install ${moduleName}`);
        return;
      }
      const row = await api.goldInspect(connectionId, goldId);
      setGoldHost(row);
      setCalloutTitle("Invoicing installed on this connection");
      setApplyNote(
        row.host_ready
          ? "Invoicing (account) is on this connection. Promote the CBN zip next, then Open Accounting Settings."
          : row.message || res.message,
      );
    } catch (err) {
      reportApiError(err, setError, { fallback: "Could not install Invoicing on this connection", toast: true });
    } finally {
      setBusy(null);
    }
  }

  async function reverifyAuthoringGate() {
    if (!session) return;
    setError(null);
    setBusy("reverify");
    try {
      const verified = await api.reverifyOptionAAuthoring({
        connection_id: connectionId,
        session_id: session.id,
        draft: session.artifact ?? undefined,
      });
      if (verified.session) setSession(verified.session);
      setCalloutTitle(verified.ok ? "Authoring gate passed" : "Authoring gate still blocked");
      setApplyNote(
        verified.message ||
          (verified.ok
            ? "Authoring gate passed — zip and sandbox unlocked. Do not click Install this app."
            : "Authoring gate still has findings. Zip stays locked. Promote stays human."),
      );
    } catch (err) {
      reportApiError(err, setError, {
        fallback: "Could not re-check the authoring gate — restart uvicorn on :8001 without --reload",
        toast: true,
      });
    } finally {
      setBusy(null);
    }
  }

  async function installAuthoredHostModule(offer: HostInstallOffer, phrase: string) {
    if (!offer.module || phrase !== CONFIRM_PHRASE) return;
    setError(null);
    setBusy("install-host");
    let installed = false;
    try {
      const res = await api.installCommunityModule(connectionId, offer.module);
      if (!res.ok) {
        setError(res.message || `Could not install ${offer.label}`);
        return;
      }
      installed = true;
      setBusy("reverify");
      const verified = await api.reverifyOptionAAuthoring({
        connection_id: connectionId,
        session_id: session?.id,
        draft: session?.artifact ?? undefined,
      });
      if (verified.session) setSession(verified.session);
      setCalloutTitle(`${offer.label} installed on this connection`);
      setApplyNote(
        verified.ok
          ? `${offer.label} (${offer.module}) is on this connection. Authoring gate passed — zip and sandbox unlocked. Do not click Install this app. Promote stays human.`
          : verified.message ||
            `${offer.label} is installed. The authoring gate still has findings. Zip stays locked.`,
      );
    } catch (err) {
      if (installed && isApiNotFound(err)) {
        setCalloutTitle(`${offer.label} install was sent`);
        setApplyNote(
          `${offer.label} (${offer.module}) was sent to this Odoo. The authoring re-check API returned 404 — kill/restart uvicorn on :8001 without --reload, hard-refresh, then Re-check authoring gate. Do not click Install this app.`,
        );
        return;
      }
      reportApiError(err, setError, {
        fallback: `Could not install ${offer.label} on this connection`,
        toast: true,
      });
    } finally {
      setBusy(null);
    }
  }

  async function onApplyToOdoo(phrase: string) {
    if (!session) return;
    setError(null);
    setBusy("apply");
    try {
      const res = await api.applyStudioSession(session.id, {
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setApplyOpen(false);
      if (res.session) setSession(res.session);
      const menuId = res.root_menu_id;
      const warnings = (res.warnings || []).filter(Boolean);
      const menuSkipped = warnings.some((w) => /menus skipped/i.test(w));
      const host =
        inheritHost ||
        hostForOpen ||
        inheritHostModelFromDraft(res.session?.artifact ?? session.artifact ?? null);
      const hostUrl =
        !menuId && connection?.url && host
          ? odooViewUrl(connection.url, host, "list", res.open_action_id)
          : null;
      setOdooAppUrl(
        menuId && connection?.url
          ? odooMenuUrl(connection.url, menuId, res.open_action_id)
          : hostUrl,
      );
      setCalloutTitle("Applied to Odoo");
      const homeHint =
        "Look on the Odoo home grid (hard-refresh) — Apps search will not list a live-metadata app.";
      if (menuId) {
        const tile = String(
          (res.session?.artifact?.display_name as string | undefined) || liveAppName,
        );
        setApplyNote(
          `${res.message} Open in Odoo now lands on ${tile}. ${homeHint}`,
        );
      } else if (host) {
        setApplyNote(
          `${res.message} Open in Odoo opens ${hostFormName} (Invoicing → Bills if this was vendor bills) — not a new app tile.`,
        );
      } else {
        setApplyNote(
          menuSkipped
            ? `${res.message} Menus were not created (${warnings.join("; ")}). ${homeHint}`
            : `${res.message} No app menu id returned — the preview is still not live. ${homeHint}`,
        );
      }
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(err.warning);
      } else {
        reportApiError(err, setError, { fallback: "Apply failed", toast: true });
      }
    } finally {
      setBusy(null);
    }
  }

  const appTitle = preview?.title || session?.prompt_resolved?.slice(0, 40) || "App draft";
  const reviewTurns = (session?.conversation || []).filter(
    (t) => t.kind === "refine" || t.kind === "refine_result",
  );
  let latestUserRefineIdx = -1;
  reviewTurns.forEach((turn, idx) => {
    if (turn.kind === "refine" && turn.role === "user") latestUserRefineIdx = idx;
  });

  function OpenInOdooButton({ testId }: { testId?: string }) {
    if (goldOptionA && goldCanOpenSettings && goldInspect) {
      return (
        <a
          href={goldInspect.href}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-secondary"
          data-testid={testId}
          title={goldInspect.hint}
        >
          {goldInspect.label}
        </a>
      );
    }
    if (goldOptionA) {
      return (
        <button
          type="button"
          className="btn btn-secondary"
          disabled
          data-testid={testId}
          title={
            goldHost?.message ||
            "Install Invoicing on this connection, Promote the zip, then open Invoicing → Configuration → Settings. Settings → Currency is the Enterprise tease."
          }
        >
          Open Accounting Settings
        </button>
      );
    }
    if (appIsLiveOnOdoo && openInOdooUrl) {
      return (
        <a
          href={openInOdooUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-secondary"
          data-testid={testId}
          title={
            fieldPack
              ? `Opens a ${hostFormName.toLowerCase()} in Odoo — look under Invoicing, not a new app tile.`
              : `Opens ${liveAppName} in Odoo — look on the home grid, not Apps.`
          }
        >
          Open in Odoo
        </a>
      );
    }
    return (
      <button
        type="button"
        className="btn btn-secondary"
        disabled
        data-testid={testId}
        title={
          fieldPack
            ? `Apply these fields first. Then open a ${hostFormName.toLowerCase()} in Odoo to see them.`
            : "Apply this app first. The canvas is a preview — Odoo has no new menu until you apply."
        }
      >
        Open in Odoo
      </button>
    );
  }

  function OpenInViewDesignerButton({
    testId,
    compact,
  }: {
    testId?: string;
    compact?: boolean;
  }) {
    const title = !designerModel
      ? "Opens View Designer. This draft has no form model yet."
      : appIsLiveOnOdoo
        ? `Edit ${designerModel} views in View Designer`
        : fieldPack
          ? `Opens View Designer on ${hostFormName}. Apply these fields first so they exist in Odoo.`
          : "Opens View Designer. Apply this app first so the form exists in Odoo.";
    return (
      <Link
        href={designerHref}
        className="btn btn-secondary"
        data-testid={testId}
        title={title}
      >
        {compact ? "View Designer" : "Open in View Designer"}
      </Link>
    );
  }

  return (
    <div className="studio-refinement">
      <div className={`studio-page${phase === "review" || phase === "generating" ? " is-canvas" : ""}`}>
        <div className="studio-top-bar">
          <span className="badge">App Studio</span>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            {session ? (
              <button type="button" className="btn btn-secondary btn-sm" onClick={startOver}>
                Start new app
              </button>
            ) : null}
            <Link href={`/connections/${connectionId}/wizard`}>Open Draft Studio (wizard)</Link>
          </div>
        </div>

        {error && phase !== "failed" && phase !== "generating" ? (
          <div className="studio-callout studio-callout-danger" role="alert">
            <p className="studio-callout-title">Something went wrong</p>
            <p style={{ margin: 0 }}>{error}</p>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ marginTop: 8 }}
              data-testid="studio-diagnose-error"
              onClick={() => diagnoseWithExpert(error)}
            >
              Diagnose with Expert
            </button>
          </div>
        ) : null}

        {isOdooOnline ? (
          <div className="studio-callout studio-callout-warning">
            <p className="studio-callout-title">Odoo Online connection</p>
            <p style={{ margin: 0 }}>
              Metadata apply works when RPC allows — same caps as the wizard. Custom Python
              modules and full Job Autopilot sandbox are not available on Online.
            </p>
          </div>
        ) : null}

        {applyNote ? (
          <div className="studio-callout studio-callout-success">
            <p className="studio-callout-title">{calloutTitle}</p>
            <p style={{ margin: 0 }}>{applyNote}</p>
            {odooAppUrl ? (
              <a
                href={odooAppUrl}
                target="_blank"
                rel="noreferrer"
                data-testid="open-app-in-odoo"
                style={{ display: "inline-block", marginTop: 8, color: "var(--text-accent)" }}
              >
                Open in Odoo →
              </a>
            ) : goldCanOpenSettings && goldInspect ? (
              <a
                href={goldInspect.href}
                target="_blank"
                rel="noreferrer"
                data-testid="open-app-in-odoo"
                style={{ display: "inline-block", marginTop: 8, color: "var(--text-accent)" }}
              >
                {goldInspect.label} →
              </a>
            ) : null}
          </div>
        ) : null}

        {!session ? (
          <div className="studio-prompt-screen">
            <h1 className="studio-prompt-title">What should people do in Odoo?</h1>
            <p className="studio-prompt-subtitle">
              Describe it in everyday words. You’ll see a form preview first —
              nothing is installed until you say so.
            </p>
            <textarea
              id="studio-prompt"
              className="textarea"
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="On vendor bills, add a Vendor TIN field that accountants fill in before confirming."
              style={{ resize: "none", textAlign: "left" }}
            />
            <div className="studio-chip-row">
              {STUDIO_STARTER_CHIPS.map((chip) => (
                <SuggestionChip
                  key={chip}
                  label={CHIP_LABELS[chip] || chip}
                  onClick={() => setPrompt(chip)}
                />
              ))}
            </div>
            <button
              type="button"
              className="btn btn-brand"
              disabled={busy !== null || prompt.trim().length < 10}
              onClick={() => void startSession()}
            >
              {busy === "create" ? <StudioBusyLabel>Starting…</StudioBusyLabel> : "See a preview →"}
            </button>
          </div>
        ) : null}

        {session && phase === "clarify" && clarification ? (
          <ClarifyInterstitial
            clarification={clarification}
            busy={busy !== null}
            onAnswer={(mk, id, text, understanding) =>
              void submitClarify(mk, id, text, understanding)
            }
          />
        ) : null}

        {session && phase === "generating" && !error ? (
          <div className="studio-canvas-progress">
            <div className="studio-canvas-ghost" aria-hidden>
              <div className="studio-canvas-ghost-bar" />
              <div className="studio-canvas-ghost-sheet" />
            </div>
            <StudioProgress
              label={progressLabelFromJob(job)}
              detail={session.prompt_resolved?.slice(0, 160)}
            />
          </div>
        ) : null}

        {session && (phase === "failed" || (phase === "generating" && error)) ? (
          <div className="studio-callout studio-callout-danger" style={{ marginTop: "var(--space-xl)" }}>
            <p className="studio-callout-title">Generation failed</p>
            <p style={{ margin: 0 }}>{job?.error || error || "The draft job did not complete."}</p>
            <div style={{ display: "flex", gap: 8, marginTop: 12, justifyContent: "center" }}>
              <button
                type="button"
                className="btn btn-brand btn-sm"
                disabled={busy === "generate"}
                onClick={() => void retryGeneration()}
              >
                {busy === "generate" ? <StudioBusyLabel>Retrying…</StudioBusyLabel> : "Try again"}
              </button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={startOver}>
                Start over
              </button>
            </div>
          </div>
        ) : null}

        {session && phase === "review" ? (
          <div style={{ marginTop: "var(--space-xl)" }}>
            {session.artifact_consistent === false ? (
              <div className="studio-callout studio-callout-warning" style={{ marginBottom: 12 }}>
                <p className="studio-callout-title">Session resume notice</p>
                <p style={{ margin: 0 }}>
                  Artifact hash differs from the last saved turn — reload or refine to reconcile.
                </p>
              </div>
            ) : null}

            {!appIsLiveOnOdoo && !stockReuse && !refuseClone && !goldOptionA && !authoredOptionA ? (
              <div className="studio-callout" style={{ marginBottom: 12 }}>
                <p className="studio-callout-title">Preview only — not in Odoo yet</p>
                <p style={{ margin: 0 }}>
                  {fieldPack ? (
                    <>
                      This canvas shows extra fields on <strong>{hostFormName}</strong>.
                      Click <strong>Apply these fields</strong> to add them on the form
                      people already use. It does not create a new app tile.
                    </>
                  ) : (
                    <>
                      This canvas is a draft. Click <strong>Install this app</strong> to create the{" "}
                      <strong>{liveAppName}</strong> tile on the Odoo home grid (not Apps).
                      {liveAppName.toLowerCase() === "helpdesk"
                        ? " Tickets is a submenu inside Helpdesk — it will not appear as its own Apps tile."
                        : ""}
                    </>
                  )}
                </p>
              </div>
            ) : null}
            {grammarCard && !stockReuse && !refuseClone && !goldOptionA && !authoredOptionA ? (
              <div className="studio-callout" style={{ marginBottom: 12 }} data-testid="studio-grammar-card">
                <p className="studio-callout-title">What will exist in Odoo</p>
                <p style={{ margin: 0 }}>{grammarCard.summary}</p>
              </div>
            ) : null}
            {fieldPack && placementRows.length && slotCatalog.length && !goldOptionA && !authoredOptionA ? (
              <div
                className="studio-callout"
                style={{ marginBottom: 12 }}
                data-testid="studio-form-slots"
              >
                <p className="studio-callout-title">Where on {hostFormName}</p>
                <p style={{ margin: "0 0 8px" }}>
                  Fields sit next to vendor or dates, on Other Info, or on a named tab — not
                  in a nested Extension group. View Designer can still move them after Apply.
                </p>
                <div className="studio-form-slots">
                  {placementRows.map((row) => (
                    <label key={row.name} className="studio-form-slot-row">
                      <span>{row.string}</span>
                      <select
                        className="input"
                        value={row.slot}
                        disabled={busy === "refine"}
                        aria-label={`Place ${row.string}`}
                        onChange={(event) => {
                          const next = slotCatalog.find((item) => item.id === event.target.value);
                          if (!next || next.id === row.slot) return;
                          void submitRefine(`put ${row.string} ${next.phrase}`);
                        }}
                      >
                        {slotCatalog.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                </div>
              </div>
            ) : null}
            {surfaceFindings.length ? (
              <div
                className="studio-callout studio-callout-warning"
                style={{ marginBottom: 12 }}
                data-testid="studio-surface-gate"
              >
                <p className="studio-callout-title">Not ready to install</p>
                <p style={{ margin: 0 }}>
                  This draft would look amateur in Odoo. Install is off until the
                  document grammar is unique (no duplicate notebooks, no placeholder
                  name, money and approval slots filled).
                </p>
                <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                  {surfaceFindings.map((row, i) => (
                    <li key={`${row.element || "f"}-${i}`}>{row.detail}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {goldOptionA ? (
              <div className="studio-callout" style={{ marginBottom: 12 }} data-testid="studio-gold-option-a">
                <p className="studio-callout-title">
                  Option A gold{goldId ? ` — ${goldId}` : ""} (not a new app)
                </p>
                <p style={{ margin: 0 }}>
                  {goldHonesty ||
                    "Community has no ECB Service dropdown. This zip adds Central Bank of Nigeria and writes stock res.currency.rate."}{" "}
                  <strong>Start new app</strong> if you are still looking at Purchase Requests — do not Install this onto that form.
                </p>
                {goldSettings?.fields?.length ? (
                  <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                    {goldSettings.fields.map((f) => (
                      <li key={f.name}>
                        {f.string}{" "}
                        <span style={{ color: "var(--text-secondary)" }}>({f.name})</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <p style={{ margin: "8px 0 0" }}>
                  Sandbox prove does not install Invoicing on <em>this</em> connection. Settings →
                  search Currency → Automatic Currency Rates is Community’s Enterprise upgrade tease
                  (no ECB Service). Flow: install Invoicing here if missing → sandbox smoke →{" "}
                  <strong>Promote</strong> → Invoicing → Configuration → Settings → Central Bank of
                  Nigeria. Not a new app tile. Not Purchase Request Currency.
                </p>
                {goldHost?.host_ready === false ? (
                  <p
                    style={{ margin: "8px 0 0" }}
                    data-testid="studio-gold-host-missing"
                    className="studio-callout-title"
                  >
                    {goldHost.message}
                  </p>
                ) : null}
                <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
                  {goldNeedsInvoicing ? (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={Boolean(busy) || isOdooOnline}
                      data-testid="studio-gold-install-invoicing"
                      onClick={() => setInstallOpen(true)}
                    >
                      {busy === "install-host" ? (
                        <StudioBusyLabel>Installing…</StudioBusyLabel>
                      ) : (
                        "Install Invoicing on this connection"
                      )}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={Boolean(busy)}
                    onClick={() => void downloadGoldZip()}
                  >
                    {busy === "zip" ? <StudioBusyLabel>Exporting…</StudioBusyLabel> : "Download module zip"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={Boolean(busy) || isOdooOnline}
                    title={isOdooOnline ? "Sandbox prove is not available on Odoo Online" : undefined}
                    onClick={() => void proveGoldSandbox()}
                  >
                    {busy === "prove" ? <StudioBusyLabel>Sandbox…</StudioBusyLabel> : "Sandbox install & smoke"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={Boolean(busy) || !goldCanPromote}
                    data-testid="studio-gold-promote"
                    title={
                      isOdooOnline
                        ? "Promote is not available on Odoo Online"
                        : goldCanPromote
                          ? "Install the sandbox-validated zip on this connection (pulls Invoicing if needed)"
                          : "Run Sandbox install & smoke first (validation lasts 2 hours)"
                    }
                    onClick={() => setPromoteOpen(true)}
                  >
                    {busy === "promote" ? (
                      <StudioBusyLabel>Promoting…</StudioBusyLabel>
                    ) : goldPromoted ? (
                      "Promote again"
                    ) : (
                      "Promote to this connection"
                    )}
                  </button>
                  {goldCanOpenSettings && goldInspect ? (
                    <a
                      href={goldInspect.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-secondary btn-sm"
                      data-testid="studio-gold-open-odoo"
                      title={goldInspect.hint}
                    >
                      {goldInspect.label}
                    </a>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled
                      data-testid="studio-gold-open-odoo"
                      title={
                        goldHost?.message ||
                        "Promote first. Then Invoicing → Configuration → Settings — not Settings → Currency."
                      }
                    >
                      Open Accounting Settings
                    </button>
                  )}
                </div>
                <p style={{ margin: "8px 0 0", color: "var(--text-secondary)", fontSize: 13 }}>
                  {goldCanOpenSettings && goldInspect
                    ? goldInspect.hint
                    : goldHost?.message ||
                      "Open Accounting Settings stays off until Invoicing is on this connection and you Promote."}
                </p>
              </div>
            ) : null}

            {authoredOptionA ? (
              <div className="studio-callout" style={{ marginBottom: 12 }} data-testid="studio-authored-option-a">
                <p className="studio-callout-title">
                  {authoringPassed
                    ? "Option A module — zip and sandbox unlocked"
                    : "Option A module (not a new app)"}
                </p>
                <p style={{ margin: 0 }}>
                  {goldHonesty ||
                    "This extends a stock form (for example Sales) with Python — markup %, WHT on markup only, sales not purchases. Live Install cannot land that code."}{" "}
                  {authoringRetryable ? (
                    busy === "generate"
                      ? "Repairing incomplete JSON automatically — diagnosis stays locked."
                      : "Authoring did not finish, so zip stayed locked. Retry authoring if this is still here after a moment. Do not click Install this app."
                  ) : (
                    <>
                      Download the zip after the authoring gate passes, sandbox-prove, then{" "}
                      <strong>Promote</strong>. Do not click Install this app.
                    </>
                  )}
                </p>
                {hostInstallOffers.length > 0 ? (
                  <HostInstallPanel
                    offers={hostInstallOffers}
                    busy={busy === "install-host" || busy === "reverify"}
                    disabled={Boolean(busy) || isOdooOnline}
                    disabledReason={
                      isOdooOnline
                        ? "Odoo Online cannot install Community apps from here"
                        : undefined
                    }
                    onInstall={(offer, phrase) => void installAuthoredHostModule(offer, phrase)}
                  />
                ) : null}
                {leftoverAuthoringFindings.length > 0 ? (
                  <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                    {leftoverAuthoringFindings.slice(0, 8).map((row, i) => (
                      <li key={`auth-${i}`}>
                        {row.code ? `${row.code}: ` : ""}
                        {row.message}
                        {row.file ? ` (${row.file})` : ""}
                      </li>
                    ))}
                  </ul>
                ) : null}
                <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
                  {authoringRetryable ? (
                    <button
                      type="button"
                      className="btn btn-brand btn-sm"
                      disabled={Boolean(busy)}
                      data-testid="studio-retry-authoring"
                      onClick={() => void retryGeneration()}
                    >
                      {busy === "generate" ? <StudioBusyLabel>Repairing…</StudioBusyLabel> : "Retry authoring"}
                    </button>
                  ) : null}
                  {!authoringPassed && !authoringRetryable ? (
                    <button
                      type="button"
                      className="btn btn-brand btn-sm"
                      disabled={Boolean(busy)}
                      data-testid="studio-reverify-authoring"
                      onClick={() => void reverifyAuthoringGate()}
                    >
                      {busy === "reverify" ? (
                        <StudioBusyLabel>Re-checking…</StudioBusyLabel>
                      ) : (
                        "Re-check authoring gate"
                      )}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={Boolean(busy) || !authoringPassed}
                    title={
                      authoringPassed
                        ? undefined
                        : "Authoring gate has not passed — zip stays locked"
                    }
                    onClick={() => void downloadGoldZip()}
                  >
                    {busy === "zip" ? <StudioBusyLabel>Exporting…</StudioBusyLabel> : "Download module zip"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={Boolean(busy) || isOdooOnline || !authoringPassed}
                    title={
                      isOdooOnline
                        ? "Sandbox prove is not available on Odoo Online"
                        : authoringPassed
                          ? undefined
                          : "Authoring gate has not passed — sandbox stays locked"
                    }
                    onClick={() => void proveGoldSandbox()}
                  >
                    {busy === "prove" ? <StudioBusyLabel>Sandbox…</StudioBusyLabel> : "Sandbox install & smoke"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={Boolean(busy) || !goldCanPromote}
                    title={
                      isOdooOnline
                        ? "Promote is not available on Odoo Online"
                        : goldCanPromote
                          ? "Install the sandbox-validated zip on this connection"
                          : "Run Sandbox install & smoke first (validation lasts 2 hours)"
                    }
                    onClick={() => setPromoteOpen(true)}
                  >
                    {busy === "promote" ? (
                      <StudioBusyLabel>Promoting…</StudioBusyLabel>
                    ) : goldPromoted ? (
                      "Promote again"
                    ) : (
                      "Promote to this connection"
                    )}
                  </button>
                </div>
              </div>
            ) : null}

            {stockReuse ? (
              <div className="studio-callout" style={{ marginBottom: 12 }} data-testid="studio-stock-reuse">
                <p className="studio-callout-title">Stock Community apps — no custom form</p>
                <p style={{ margin: 0 }}>
                  This draft has no x_* document to preview. Stock Purchase is RFQs and
                  vendor POs, not staff purchase requests with manager approval.
                  If you wanted that form, start a new app and keep{" "}
                  <strong>One simple document</strong> — do not pick stock-only.
                </p>
                {stockApps.length ? (
                  <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                    {stockApps.map((app) => (
                      <li key={app.id}>
                        {app.label}{" "}
                        <span style={{ color: "var(--text-secondary)" }}>({app.id})</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <p style={{ margin: "8px 0 0" }}>
                  <Link href={`/connections/${connectionId}/job`}>
                    Open Job Autopilot
                  </Link>{" "}
                  for sandbox install of named stock apps.
                </p>
              </div>
            ) : null}

            <div className="studio-chip-row studio-mobile-tabs" style={{ justifyContent: "flex-start", marginBottom: 12 }}>
              <button
                type="button"
                className={`chip ${mobileTab === "preview" ? "is-selected" : ""}`}
                onClick={() => setMobileTab("preview")}
              >
                Preview
              </button>
              <button
                type="button"
                className={`chip ${mobileTab === "chat" ? "is-selected" : ""}`}
                onClick={() => setMobileTab("chat")}
              >
                Refine
              </button>
            </div>

            <ReviewRefineLayout
              mobileTab={mobileTab}
              header={
                <div className="panel-header">
                  <div className="breadcrumb">
                    <span>{appTitle}</span>
                    <span aria-hidden>›</span>
                    <span className="current">{preview?.title || "Form preview"}</span>
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <OpenInViewDesignerButton compact />
                    <OpenInOdooButton />
                    <ModelTierBadge
                      provider={session.provider_used}
                      fallbackUsed={session.fallback_used}
                    />
                  </div>
                </div>
              }
              preview={
                preview || session?.artifact ? (
                  <div data-testid="draft-odoo-preview">
                    <DraftOdooPreview
                      draft={session?.artifact ?? null}
                      breadcrumb={appTitle}
                      formPreview={preview}
                      flashFieldId={flashId}
                      highlightedFieldIds={highlightIds}
                    />
                  </div>
                ) : (
                  <p style={{ color: "var(--text-secondary)", fontSize: "var(--font-size-sm)" }}>
                    No custom form in this draft. Describe what people should do in Odoo and try again.
                  </p>
                )
              }
              chat={
                <>
                  <div className="studio-chat-toolbar">
                    <span className="studio-chat-toolbar-label">Refine trail</span>
                    <RefineHistoryPopover
                      conversation={session?.conversation}
                      onReuse={(content) => setRefineInput(content)}
                      onUndo={(instruction) => void submitRefine(instruction)}
                      undoBusy={busy === "refine"}
                    />
                  </div>
                  {reviewTurns.length === 0 ? (
                    <ChatBubble role="assistant">
                      Preview is on the left. Ask for a change and the form updates —
                      remove a field, make one required, or add one.
                    </ChatBubble>
                  ) : null}
                  {reviewTurns.map((turn, idx) => {
                    const isUserRefine = turn.kind === "refine" && turn.role === "user";
                    const undoInstruction =
                      isUserRefine && idx === latestUserRefineIdx
                        ? undoInstructionForRefine(turn.content, true)
                        : null;
                    return (
                      <div
                        key={`${turn.at || idx}-${turn.kind}`}
                        className={isUserRefine ? "studio-user-turn" : undefined}
                      >
                        <ChatBubble
                          role={
                            turn.role === "user"
                              ? "user"
                              : turn.role === "system"
                                ? "system"
                                : "assistant"
                          }
                        >
                          {turn.content}
                        </ChatBubble>
                        {undoInstruction ? (
                          <button
                            type="button"
                            className="studio-bubble-undo"
                            disabled={busy === "refine"}
                            data-testid="refine-chat-undo"
                            title="Undo this change (sends “oops”)"
                            onClick={() => void submitRefine(undoInstruction)}
                          >
                            Undo
                          </button>
                        ) : null}
                      </div>
                    );
                  })}
                  {localRefineError ? (
                    <ChatBubble role="assistant">{localRefineError}</ChatBubble>
                  ) : null}
                </>
              }
              chatInput={
                <div className="chat-composer">
                  {refineChips.length ? (
                    <div className="studio-chip-row studio-refine-chips">
                      {refineChips.map((chip) => (
                        <SuggestionChip
                          key={chip}
                          label={chip}
                          disabled={busy === "refine"}
                          onClick={() => setRefineInput(chip)}
                        />
                      ))}
                    </div>
                  ) : null}
                  <div className="chat-input-row">
                    <input
                      type="text"
                      className="input"
                      placeholder={
                        fieldPack
                          ? `Describe a change — e.g. make ${hostFormName.toLowerCase()} fields required`
                          : "Describe a change — e.g. remove the priority field"
                      }
                      value={refineInput}
                      onChange={(e) => setRefineInput(e.target.value)}
                      disabled={busy === "refine"}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && refineInput.trim().length >= 3) {
                          void submitRefine();
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn-primary btn-icon"
                      aria-label="Send refinement"
                      disabled={busy === "refine" || refineInput.trim().length < 3}
                      onClick={() => void submitRefine()}
                    >
                      {busy === "refine" ? <Spokes className="studio-loader-spokes" aria-hidden /> : "→"}
                    </button>
                  </div>
                </div>
              }
              footer={
                <>
                  <OpenInViewDesignerButton testId="open-view-designer" />
                  <OpenInOdooButton testId="open-in-odoo" />
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!canApply || stockReuse || refuseClone || goldOptionA || authoredOptionA || surfaceBlocked || busy === "apply"}
                    title={
                      goldOptionA
                        ? "Option A gold — zip → sandbox → Promote. Live Install cannot land CBN Python or cron."
                      : authoredOptionA
                        ? "Option A module — zip → sandbox → Promote. Live Install cannot land markup/WHT Python."
                      : stockReuse
                        ? "Empty stock-reuse spec — use Job Autopilot, not Install."
                        : surfaceBlocked
                          ? "Document grammar is not unique yet — Install is off."
                        : (applyBlocked ?? undefined)
                    }
                    onClick={() => setApplyOpen(true)}
                  >
                    {busy === "apply" ? (
                      <StudioBusyLabel>Applying…</StudioBusyLabel>
                    ) : fieldPack ? (
                      "Apply these fields"
                    ) : (
                      "Install this app"
                    )}
                  </button>
                </>
              }
            />
            {applyBlocked ? (
              <div className="studio-callout studio-callout-warning" style={{ marginTop: 12 }}>
                <p className="studio-callout-title">Apply blocked on this connection</p>
                <p style={{ margin: 0 }}>{applyBlocked}</p>
              </div>
            ) : null}
          </div>
        ) : null}

        <ConfirmDialogV2
          open={installOpen}
          title="Install Invoicing on this connection"
          warning="Installs Community Invoicing (account) on this live Odoo so Accounting Settings exist. Sandbox prove did not do that."
          risks={[
            "Installs the stock account module and its depends",
            "Does not install CBN — Promote the zip after this",
            "Settings → search Currency remains an Enterprise tease until Promote",
          ]}
          phrase={CONFIRM_PHRASE}
          busy={busy === "install-host"}
          riskLevel="danger"
          snapshotNote="Prefer a sandbox connection before production."
          onCancel={() => setInstallOpen(false)}
          onConfirm={(phrase) => void installGoldHostModule(phrase)}
        />
        <ConfirmDialogV2
          open={promoteOpen}
          title="Promote validated module"
          warning="Installs the sandbox-validated Python module on this live Odoo connection. The ephemeral sandbox is already gone."
          risks={
            authoredOptionA
              ? [
                  "Adds Python/XML on stock models (for example sale.order markup)",
                  "Does not create a new home-grid tile — inspect the stock Sales form",
                  "Never invents account.tax — WHT must use an existing tax xmlid",
                  "Only promote after sandbox validation passed (2 hour token)",
                ]
              : [
                  "Adds Python, views, and cron jobs (CBN writes stock res.currency.rate)",
                  "Does not create a new app tile — inspect Accounting Settings after",
                  "Uninstall may not fully reverse rates or cron",
                  "Only promote after sandbox validation passed (2 hour token)",
                ]
          }
          phrase={CONFIRM_PHRASE}
          busy={busy === "promote"}
          riskLevel="danger"
          snapshotNote="Prefer a sandbox connection before production. Promote stays human."
          onCancel={() => setPromoteOpen(false)}
          onConfirm={(phrase) => void promoteGoldModule(phrase)}
        />
        <ConfirmDialogV2
          open={applyOpen}
          title={fieldPack ? "Add these fields in Odoo" : "Apply draft to Odoo"}
          warning={
            fieldPack
              ? `Adds the fields on this preview to the existing ${hostFormName} form. Does not create a new app on the home screen.`
              : "Applies this App Studio draft: models, fields, views, menus, and smart buttons on the live connection."
          }
          risks={
            fieldPack
              ? [
                  `Adds fields on the stock ${hostFormName} form via RPC`,
                  "Does not create a new home-grid tile",
                  "Prefer a sandbox connection before production",
                  ...(isOdooOnline
                    ? ["Odoo Online: no custom Python module install — metadata apply only"]
                    : []),
                ]
              : [
                  "Creates ir.model / fields / views / menus via RPC",
                  "May rewrite primary form arches for custom x_* models",
                  "Prefer a sandbox connection before production",
                  ...(isOdooOnline
                    ? ["Odoo Online: no custom Python module install — metadata apply only"]
                    : []),
                ]
          }
          phrase={CONFIRM_PHRASE}
          busy={busy === "apply"}
          riskLevel="danger"
          snapshotNote="Take a metadata snapshot first if this is production."
          onCancel={() => setApplyOpen(false)}
          onConfirm={(phrase) => void onApplyToOdoo(phrase)}
        />
      </div>
    </div>
  );
}
