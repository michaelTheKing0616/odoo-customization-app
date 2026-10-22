"use client";

import { useCallback, useRef, useState } from "react";
import type { Connection, JobRow } from "@/lib/api";
import type { StudioSession } from "@/lib/studio-session";
import type { StudioErrorStep } from "@/lib/studio-journey";
import type { GoldHostStatus } from "./StudioOptionAPanel";

export function useStudioState() {
  const [prompt, setPrompt] = useState("");
  const [flashAstEnrich, setFlashAstEnrich] = useState<boolean | null>(null);
  const [flashAstEnrichHelp, setFlashAstEnrichHelp] = useState(
    "On: optional Flash AST fill (same path as AI_INTENT_LLM). Off: deterministic floor only.",
  );

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
  const [goldHost, setGoldHost] = useState<GoldHostStatus | null>(null);
  const [installOpen, setInstallOpen] = useState(false);
  const [mobileTab, setMobileTab] = useState<"preview" | "chat">("preview");
  const refineComposerRef = useRef<HTMLTextAreaElement | null>(null);

  const beginStudioAction = useCallback(() => {
    setError(null);
    setErrorStep(null);
    setApplyNote(null);
  }, []);

  const failStudio = useCallback((step: StudioErrorStep, message: string, keepNote = false) => {
    setErrorStep(step);
    setError(message);
    if (!keepNote) setApplyNote(null);
  }, []);

  return {
    prompt,
    setPrompt,
    flashAstEnrich,
    setFlashAstEnrich,
    flashAstEnrichHelp,
    setFlashAstEnrichHelp,
    session,
    setSession,
    job,
    setJob,
    busy,
    setBusy,
    error,
    setError,
    errorStep,
    setErrorStep,
    refineInput,
    setRefineInput,
    localRefineError,
    setLocalRefineError,
    highlightIds,
    setHighlightIds,
    flashId,
    setFlashId,
    connection,
    setConnection,
    applyOpen,
    setApplyOpen,
    promoteOpen,
    setPromoteOpen,
    applyNote,
    setApplyNote,
    calloutTitle,
    setCalloutTitle,
    odooAppUrl,
    setOdooAppUrl,
    goldValidationId,
    setGoldValidationId,
    goldZipBase64,
    setGoldZipBase64,
    goldPromoted,
    setGoldPromoted,
    lastSandboxFault,
    setLastSandboxFault,
    goldHost,
    setGoldHost,
    installOpen,
    setInstallOpen,
    mobileTab,
    setMobileTab,
    refineComposerRef,
    beginStudioAction,
    failStudio,
  };
}

export type StudioState = ReturnType<typeof useStudioState>;
