"use client";

import { useEffect } from "react";
import { useShellOptional } from "@/context/ShellContext";

export function diagnoseWithExpert(errorText: string) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent("expert:diagnose", { detail: { errorText } }),
  );
}

export function ExpertDiagnoseListener() {
  const shell = useShellOptional();

  useEffect(() => {
    if (!shell) return;
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ errorText: string }>).detail;
      shell.openExpert({
        question: "Diagnose this error on my connection",
        errorText: detail.errorText,
        autoSubmit: true,
        freshThread: true,
      });
    };
    window.addEventListener("expert:diagnose", handler);
    return () => window.removeEventListener("expert:diagnose", handler);
  }, [shell]);

  return null;
}
