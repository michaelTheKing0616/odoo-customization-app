"use client";

import { useEffect, useState } from "react";

import { Callout } from "@/components/ui/Callout";

type OverlayMessage = {
  type: string;
  fieldName?: string;
  tag?: string;
};

type Props = {
  iframeRef: React.RefObject<HTMLIFrameElement | null>;
  onSelect: (fieldName: string) => void;
};

/** Listens for postMessage field picks from the proxied Odoo overlay (UIX-6). */
export function OverlayEditor({ iframeRef, onSelect }: Props) {
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    function onMessage(ev: MessageEvent<OverlayMessage>) {
      if (ev.source !== iframeRef.current?.contentWindow) return;
      const data = ev.data;
      if (!data || typeof data !== "object") return;
      if (data.type === "oc-overlay-hover" && data.fieldName) {
        setHover(data.fieldName);
      }
      if (data.type === "oc-overlay-select" && data.fieldName) {
        onSelect(data.fieldName);
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [iframeRef, onSelect]);

  return (
    <Callout variant="info" title="Live overlay" data-testid="overlay-editor">
      Click a field in the preview frame to select it for inherit edits.
      {hover ? ` Hover: ${hover}` : ""}
      <p className="mt-2 text-xs text-[var(--oc-muted)]">
        Not in v1: add new model areas, complex restructures — use View Designer. Every save
        shows generated xpath in the inspector.
      </p>
    </Callout>
  );
}
