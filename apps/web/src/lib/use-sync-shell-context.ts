"use client";

import { useEffect } from "react";
import { useShellOptional } from "@/context/ShellContext";

export function useSyncShellContext(patch: {
  model?: string;
  draftSummary?: string;
  viewType?: string;
  triggerType?: string;
}) {
  const shell = useShellOptional();
  useEffect(() => {
    if (!shell) return;
    shell.setUiContext(patch);
  }, [shell, patch.model, patch.draftSummary, patch.viewType, patch.triggerType, patch]);
}
