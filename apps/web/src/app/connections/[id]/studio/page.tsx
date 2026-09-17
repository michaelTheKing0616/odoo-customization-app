"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ClarifyInterstitial } from "@/components/studio/ClarifyInterstitial";
import { ModelTierBadge } from "@/components/studio/ModelTierBadge";
import { ReviewRefineLayout } from "@/components/studio/ReviewRefineLayout";
import { StudioApplyBar } from "@/components/studio/StudioApplyBar";
import { StudioBriefScreen } from "@/components/studio/StudioBriefScreen";
import { StudioBusyLabel } from "@/components/studio/StudioBusyLabel";
import { StudioChatThread } from "@/components/studio/StudioChatThread";
import { StudioHonestyBanners } from "@/components/studio/StudioHonestyBanners";
import {
  StudioOpenInOdoo,
  StudioOpenInViewDesigner,
} from "@/components/studio/StudioOpenLinks";
import { StudioOptionAPanel } from "@/components/studio/StudioOptionAPanel";
import { StudioPreviewPane } from "@/components/studio/StudioPreviewPane";
import { StudioProgress } from "@/components/studio/StudioProgress";
import { StudioRefineComposer } from "@/components/studio/StudioRefineComposer";
import { StudioShell } from "@/components/studio/StudioShell";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Callout } from "@/components/ui/Callout";
import { Button } from "@/components/ui/Button";
import {
  api,
  ClarificationRequiredError,
  ConfirmationRequiredError,
  Connection,
  JobRow,
} from "@/lib/api";
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
import { odooMenuUrl, odooViewUrl, goldOptionAInspectLink, preferHostListActionId } from "@/lib/odoo-urls";
import { JobPollError, pollJob } from "@/lib/jobs";
import {
  forgetStudioSession,
  loadRememberedStudioSession,
  loadStashedStudioPrompt,
  rememberStudioSession,
  studioAppIsLiveOnOdoo,
  studioApplyMenuTarget,
  sessionWithClarification,
  studioPhaseFromSession,
  type StudioSession,
} from "@/lib/studio-session";
import {
  draftFromJobResult,
  progressLabelFromJob,
  studioErrorTitle,
  studioJourneyFromPhase,
  type StudioErrorStep,
} from "@/lib/studio-journey";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import "@/styles/studio-refinement.css";

const POLL_MS = 2500;
const POLL_ATTEMPTS = 900;
const CONFIRM_PHRASE = "I understand the risks";

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
  const [errorStep, setErrorStep] = useState<StudioErrorStep | null>(null);
  const [refineInput, setRefineInput] = useState("");
  const [localRefineError, setLocalRefineError] = useState<string | null>(null);
  const [highlightIds, setHighlightIds] = useState<string[]>([]);
  const [flashId, setFlashId] = useState<string | null>(null);
  const [connection, setConnection] = useState<Connection | null>(null);
  const [applyOpen, setApplyOpen] = useState(false);
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [applyNote, setApplyNote] = useState<string | null>(null);
  const [calloutTitle, setCalloutTitle] = useState("Applied to Odoo");
  const [odooAppUrl, setOdooAppUrl] = useState<string | null>(null);
  const [goldValidationId, setGoldValidationId] = useState<string | null>(null);
  const [goldZipBase64, setGoldZipBase64] = useState<string | null>(null);
  const [goldPromoted, setGoldPromoted] = useState(false);
  const [lastSandboxFault, setLastSandboxFault] = useState<string | null>(null);
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
  }, [connectionId, router]);


  function beginStudioAction() {
    setError(null);
    setErrorStep(null);
    setApplyNote(null);
  }

  function failStudio(step: StudioErrorStep, message: string, keepNote = false) {
    setErrorStep(step);
    setError(message);
    if (!keepNote) setApplyNote(null);
  }

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

  // After Option A Promote, resolve Quotations (etc.) act_window — bare model= lands on Discuss.
  useEffect(() => {
    if (!connectionId || goldOptionA) return;
    if (!(goldPromoted || optionAHostLive)) return;
    const host = hostForOpen;
    if (!host || applyTarget.openActionId) return;
    const base = connection?.url?.replace(/\/$/, "") || "";
    if (!base) return;
    let cancelled = false;
    (async () => {
      try {
        const actions = await api.listWindowActions(connectionId, {
          model: host,
          standaloneOnly: true,
        });
        if (cancelled) return;
        const actionId = preferHostListActionId(actions, host);
        if (!actionId) return;
        const href = odooViewUrl(base, host, "list", actionId);
        setOdooAppUrl(href);
        setSession((s) => {
          if (!s?.artifact) return s;
          const prev = s.artifact._studio_apply;
          const prior =
            prev && typeof prev === "object" && !Array.isArray(prev)
              ? (prev as Record<string, unknown>)
              : {};
          if (Number(prior.open_action_id) === actionId) return s;
          return {
            ...s,
            artifact: {
              ...s.artifact,
              _studio_apply: {
                ...prior,
                root_menu_id: null,
                open_action_id: actionId,
                host_model: host,
                applied: true,
                via: prior.via || "option_a_promote",
              },
            },
          };
        });
      } catch {
        /* best-effort */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    connectionId,
    connection?.url,
    goldOptionA,
    goldPromoted,
    optionAHostLive,
    hostForOpen,
    applyTarget.openActionId,
  ]);

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
    if (!connectionId?.trim()) {
      setError("Open App Studio from a connection page, then try again.");
      return;
    }
    setError(null);
    setBusy("create");
    try {
      const created = await api.createStudioSession({
        connection_id: connectionId.trim(),
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
    beginStudioAction();
    setBusy("zip");
    try {
      const res = await api.exportModuleSpecZip(connectionId, { spec });
      if (!res.zip_base64) {
        failStudio("zip", "Zip export returned no file.");
        return;
      }
      downloadZipBase64(String(res.module || spec.technical_name || "currency_rate_cbn"), res.zip_base64);
      setCalloutTitle("Module zip downloaded");
      setApplyNote(
        authoredOptionA
          ? "Downloaded the Option A zip. Next: Sandbox install & smoke (proof only), then Promote. Do not click Install this app."
          : "Downloaded the Option A zip. Next: Sandbox install & smoke (proof only), then Promote onto this connection. Open Accounting Settings is this Odoo — not the ephemeral sandbox.",
      );
    } catch (err) {
      failStudio("zip", err instanceof Error ? err.message : "Zip export failed");
    } finally {
      setBusy(null);
    }
  }

  async function proveGoldSandbox() {
    const spec = session?.artifact;
    if (!spec) return;
    beginStudioAction();
    setBusy("prove");
    try {
      const res = await api.proveOptionA(connectionId, { spec });
      if (res.draft) {
        setSession((s) => (s ? { ...s, artifact: res.draft as Record<string, unknown> } : s));
      }
      if (res.ok) {
        setLastSandboxFault(null);
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
        const sandboxMsg = (res.sandbox as { message?: string } | undefined)?.message;
        const msg =
          sandboxMsg ||
          (res.smoke as { message?: string } | undefined)?.message ||
          res.message ||
          "Sandbox prove failed";
        setLastSandboxFault(sandboxMsg || msg);
        const step =
          /repair budget|sandbox repair attempts|Repair with AI/i.test(res.message || "")
            ? "repair"
            : "sandbox";
        failStudio(step, res.message || msg);
        setCalloutTitle("Applied to Odoo");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Sandbox prove failed";
      setLastSandboxFault(msg);
      failStudio("sandbox", msg);
    } finally {
      setBusy(null);
    }
  }

  async function repairGoldWithAi() {
    const spec = session?.artifact;
    if (!spec) return;
    beginStudioAction();
    setBusy("repair");
    try {
      const fault =
        lastSandboxFault ||
        String(
          ((spec as Record<string, unknown>)._option_a_smoke as { message?: string } | undefined)
            ?.message ||
            ((spec as Record<string, unknown>)._sandbox_install as { message?: string } | undefined)
              ?.message ||
            "",
        );
      const res = await api.repairOptionAFeedback(connectionId, {
        spec,
        error_text: fault,
        retry_sandbox: true,
      });
      if (res.draft) {
        setSession((s) => (s ? { ...s, artifact: res.draft as Record<string, unknown> } : s));
      }
      if (res.ok && res.validation_id && res.zip_base64) {
        setLastSandboxFault(null);
        setGoldValidationId(res.validation_id);
        setGoldZipBase64(res.zip_base64);
        setGoldPromoted(false);
        setCalloutTitle("Sandbox proved after AI repair");
        setApplyNote(
          res.message ||
            "AI repair + sandbox passed. Promote stays human. Do not click Install this app.",
        );
        return;
      }
      const sandboxMsg = (res.sandbox as { message?: string } | undefined)?.message;
      const msg =
        res.feedback_repair?.message ||
        res.message ||
        sandboxMsg ||
        "AI repair did not clear the sandbox Fault";
      if (sandboxMsg) setLastSandboxFault(sandboxMsg);
      failStudio("repair", msg);
      if (res.feedback_repair?.applied) {
        setCalloutTitle("AI patched the module");
        setApplyNote(
          "The model patched files from the sandbox Fault. Retry Sandbox install & smoke, or Repair with AI again if budget remains. Do not click Install this app.",
        );
      }
    } catch (err) {
      failStudio("repair", err instanceof Error ? err.message : "AI repair failed");
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
      const host =
        inheritHostModelFromDraft(spec) ||
        inheritHostModelFromDraft(session?.artifact ?? null) ||
        inheritHost;
      const base = connection?.url?.replace(/\/$/, "") || "";
      let openActionId: number | null = null;
      let stampMsg = "";
      if (!goldOptionA && session?.id) {
        try {
          const stamped = await api.stampOptionAPromote(session.id);
          if (stamped.id) setSession(stamped);
          else if (stamped.session) setSession(stamped.session);
          openActionId =
            typeof stamped.open_action_id === "number" ? stamped.open_action_id : null;
          const stampHost =
            (typeof stamped.host_model === "string" && stamped.host_model) || host;
          stampMsg = String(stamped.message || "");
          if (Array.isArray(stamped.host_install) && stamped.host_install.length) {
            setApplyNote(stampMsg);
          }
          if (stampHost && base) {
            setOdooAppUrl(odooViewUrl(base, stampHost, "list", openActionId));
          }
        } catch {
          /* fall through to client-side resolve */
        }
      }
      if (!goldOptionA && host && base && !openActionId) {
        try {
          const actions = await api.listWindowActions(connectionId, {
            model: host,
            standaloneOnly: true,
          });
          openActionId = preferHostListActionId(actions, host);
        } catch {
          /* action resolve is best-effort */
        }
        const href = odooViewUrl(base, host, "list", openActionId);
        setOdooAppUrl(href);
        setSession((s) => {
          if (!s?.artifact) return s;
          return {
            ...s,
            artifact: {
              ...s.artifact,
              _studio_apply: {
                root_menu_id: null,
                open_action_id: openActionId,
                host_model: host,
                applied: true,
                via: "option_a_promote",
              },
            },
          };
        });
      }
      try {
        if (goldOptionA && goldId) {
          const row = await api.goldInspect(connectionId, goldId);
          setGoldHost(row);
        }
      } catch {
        /* inspect is best-effort after promote */
      }
      const hostLabel = hostFormName || host || "the stock form";
      if (!stampMsg || !/missing/i.test(stampMsg)) {
        setApplyNote(
          goldOptionA
            ? res.message ||
                `Promoted ${tech} onto this connection. Open Invoicing → Configuration → Settings (not Settings → Currency). Service = Central Bank of Nigeria → Update now → Currencies → USD → Rates.`
            : `${res.message || `Promoted ${tech} onto this connection.`} ${
                stampMsg ||
                `Open ${hostLabel} via Sales → Quotations (not Discuss, not a new Apps tile). Markup % is on the quotation form.`
              } Do not click Install this app.`,
        );
      }
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
        setApplyNote(`${res.message} Open in Odoo now lands on ${tile}. ${homeHint}`);
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

  return (
    <StudioShell
      connectionId={connectionId}
      journey={journey}
      canvas={canvas}
      hasSession={Boolean(session)}
      onStartNew={startOver}
    >
      {error && phase !== "failed" && phase !== "generating" ? (
        <Callout
          variant="danger"
          title={studioErrorTitle(errorStep, error)}
          className="mb-4"
          actions={
            <Button
              type="button"
              variant="ghost"
              size="sm"
              data-testid="studio-diagnose-error"
              onClick={() => diagnoseWithExpert(error)}
            >
              Diagnose with Expert
            </Button>
          }
        >
          {error}
        </Callout>
      ) : null}

      {isOdooOnline ? (
        <Callout variant="warning" title="Odoo Online connection" className="mb-4">
          Metadata apply works when RPC allows — same caps as the wizard. Custom Python
          modules and full Job Autopilot sandbox are not available on Online.
        </Callout>
      ) : null}

      {!session ? (
        <StudioBriefScreen
          prompt={prompt}
          busy={busy !== null}
          onPromptChange={setPrompt}
          onStart={() => void startSession()}
        />
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
        <Callout
          variant="danger"
          title="Generation failed"
          className="mt-6"
          actions={
            <>
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
            </>
          }
        >
          {job?.error || error || "The draft job did not complete."}
        </Callout>
      ) : null}

      {session && phase === "review" ? (
        <div className="studio-review">
          <StudioHonestyBanners
            connectionId={connectionId}
            applyNote={applyNote}
            calloutTitle={calloutTitle}
            odooAppUrl={odooAppUrl}
            goldInspectHref={goldCanOpenSettings ? goldInspect?.href : null}
            goldInspectLabel={goldCanOpenSettings ? goldInspect?.label : null}
            artifactConsistent={session.artifact_consistent !== false}
            appIsLiveOnOdoo={appIsLiveOnOdoo}
            stockReuse={stockReuse}
            refuseClone={refuseClone}
            goldOptionA={goldOptionA}
            authoredOptionA={authoredOptionA}
            fieldPack={fieldPack}
            hostFormName={hostFormName}
            liveAppName={liveAppName}
            grammarCard={grammarCard}
            surfaceFindings={surfaceFindings}
            liveApplyBanner={liveApplyBanner}
            unfinishedBanner={unfinishedBanner}
            operatorSurface={operatorSurface}
            placementRows={placementRows}
            slotCatalog={slotCatalog}
            stockApps={stockApps}
            applyBlocked={applyBlocked}
            refineBusy={busy === "refine"}
            onPlaceField={(fieldLabel, phrase) =>
              void submitRefine(`put ${fieldLabel} ${phrase}`)
            }
          />

          <StudioOptionAPanel
            goldOptionA={goldOptionA}
            authoredOptionA={authoredOptionA}
            goldId={goldId}
            goldHonesty={goldHonesty}
            goldSettings={goldSettings}
            goldHost={goldHost}
            goldInspect={goldInspect}
            goldNeedsInvoicing={Boolean(goldNeedsInvoicing)}
            goldCanPromote={goldCanPromote}
            goldCanOpenSettings={goldCanOpenSettings}
            goldPromoted={goldPromoted}
            authoringPassed={authoringPassed}
            authoringRetryable={authoringRetryable}
            hostInstallOffers={hostInstallOffers}
            leftoverAuthoringFindings={leftoverAuthoringFindings}
            isOdooOnline={Boolean(isOdooOnline)}
            busy={busy}
            onInstallInvoicing={() => setInstallOpen(true)}
            onDownloadZip={() => void downloadGoldZip()}
            onProveSandbox={() => void proveGoldSandbox()}
            onRepairWithAi={() => void repairGoldWithAi()}
            onPromote={() => setPromoteOpen(true)}
            onRetryAuthoring={() => void retryGeneration()}
            onReverify={() => void reverifyAuthoringGate()}
            onInstallHost={(offer, phrase) => void installAuthoredHostModule(offer, phrase)}
            openInOdooHref={!goldOptionA && goldPromoted ? openInOdooUrl : null}
            openInOdooLabel={
              hostForOpen ? `Open ${hostFormName}` : "Open in Odoo"
            }
          />

          <div className="studio-chip-row studio-mobile-tabs">
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
                <div className="studio-preview-toolbar">
                  <StudioOpenInViewDesigner {...designerLinkProps} compact />
                  <StudioOpenInOdoo {...openLinkProps} />
                  <ModelTierBadge
                    provider={session.provider_used}
                    fallbackUsed={session.fallback_used}
                  />
                </div>
              </div>
            }
            preview={
              <StudioPreviewPane
                draft={session?.artifact}
                preview={preview}
                breadcrumb={preview?.title || appTitle}
                flashFieldId={flashFieldId}
                highlightedFieldIds={highlightedFieldIds}
              />
            }
            chat={
              <StudioChatThread
                conversation={session?.conversation}
                localRefineError={localRefineError}
                refineBusy={busy === "refine"}
                onReuse={(content) => setRefineInput(content)}
                onUndo={(instruction) => void submitRefine(instruction)}
              />
            }
            chatInput={
              <StudioRefineComposer
                chips={refineChips}
                value={refineInput}
                fieldPack={fieldPack}
                hostFormName={hostFormName}
                busy={busy === "refine"}
                onChange={setRefineInput}
                onSubmit={(instruction) => void submitRefine(instruction)}
              />
            }
            footer={
              <StudioApplyBar
                designerHref={designerHref}
                designerModel={designerModel}
                appIsLiveOnOdoo={appIsLiveOnOdoo}
                fieldPack={fieldPack}
                hostFormName={hostFormName}
                liveAppName={liveAppName}
                goldOptionA={goldOptionA}
                authoredOptionA={authoredOptionA}
                goldCanOpenSettings={goldCanOpenSettings}
                goldInspect={goldInspect}
                goldHostMessage={goldHost?.message}
                openInOdooUrl={openInOdooUrl}
                canApply={canApply}
                stockReuse={stockReuse}
                refuseClone={refuseClone}
                surfaceBlocked={surfaceBlocked}
                applyBlocked={applyBlocked}
                busy={busy}
                onApply={() => setApplyOpen(true)}
              />
            }
          />
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
    </StudioShell>
  );
}
