"use client";

import { useEffect } from "react";
import { useShellOptional } from "@/context/ShellContext";

export function useSyncShellContext(patch: {
  model?: string;
  draftSummary?: string;
  viewType?: string;
  triggerType?: string;
}) {
  const setUiContext = useShellOptional()?.setUiContext;
  const { model, draftSummary, viewType, triggerType } = patch;

  useEffect(() => {
    if (!setUiContext) return;
    setUiContext({ model, draftSummary, viewType, triggerType });
  }, [setUiContext, model, draftSummary, viewType, triggerType]);
}
