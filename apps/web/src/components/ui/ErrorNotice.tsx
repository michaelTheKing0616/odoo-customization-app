"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";

type ErrorNoticeProps = {
  message: string;
  title?: string;
  className?: string;
  showDiagnose?: boolean;
  onRetry?: () => void;
  details?: string;
  /** 68: why it happened, in plain words. */
  why?: string;
  /** 68: what to do next. */
  next?: string;
  /** 68: one-click fix when there is one. */
  fix?: { label: string; onClick: () => void };
};

/** 68: short trace number people can quote to support. */
export function newTraceId(now = Date.now(), rand = Math.random()): string {
  return `ING-${now.toString(36).slice(-5).toUpperCase()}${Math.floor(rand * 1296).toString(36).padStart(2, "0").toUpperCase()}`;
}

export function supportText(o: { trace: string; title: string; message: string; details?: string; at?: Date; path?: string }): string {
  const at = (o.at ?? new Date()).toLocaleString("en-GB", { timeZone: "Africa/Lagos", dateStyle: "medium", timeStyle: "short" });
  return [`Trace ${o.trace}`, `${at} WAT`, o.path ? `Page ${o.path}` : "", `${o.title}: ${o.message}`, o.details ?? ""].filter(Boolean).join("\n");
}

export function ErrorNotice({
  message,
  title = "Request failed",
  className,
  showDiagnose = true,
  onRetry,
  details,
  why,
  next,
  fix,
}: ErrorNoticeProps) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [trace] = useState(() => newTraceId());
  const copy = async () => {
    const text = supportText({ trace, title, message, details, path: typeof window !== "undefined" ? window.location.pathname : undefined });
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`Copied. Quote ${trace} to support.`);
    } catch {
      toast.error(`Couldn't copy. Your trace number is ${trace}.`);
    }
  };
  const diagnosePayload = details || message;
  const actions = (
    <>
      {fix ? (
        <Button variant="secondary" size="sm" type="button" onClick={fix.onClick} data-testid="error-notice-fix">
          {fix.label}
        </Button>
      ) : null}
      {onRetry ? (
        <Button variant="ghost" size="sm" type="button" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
      {showDiagnose ? (
        <Button
          variant="ghost"
          size="sm"
          type="button"
          onClick={() => diagnoseWithExpert(diagnosePayload)}
        >
          Diagnose with Expert
        </Button>
      ) : null}
    </>
  );

  return (
    <Callout
      variant="danger"
      title={title}
      className={className}
      testId="error-notice"
      actions={fix || onRetry || showDiagnose ? actions : undefined}
    >
      <p data-testid="error-notice-message">{message}</p>
      {why ? <p className="mt-1 text-sm text-muted" data-testid="error-notice-why">{why}</p> : null}
      {next ? <p className="mt-1 text-sm" data-testid="error-notice-next">{next}</p> : null}
      <div className="mt-2">
        {details ? (
          <button
            type="button"
            className="mr-3 text-xs text-muted underline-offset-2 hover:underline"
            aria-expanded={detailsOpen}
            onClick={() => setDetailsOpen((open) => !open)}
            data-testid="error-notice-details-toggle"
          >
            {detailsOpen ? "Hide details" : "Show details"}
          </button>
        ) : null}
        <button type="button" className="text-xs text-muted underline-offset-2 hover:underline" onClick={() => void copy()} data-testid="error-notice-copy">
          Copy details for support
        </button>
        <span className="ml-2 font-mono text-[11px] text-muted" data-testid="error-notice-trace">{trace}</span>
        {details && detailsOpen ? (
          <pre
            className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-border-subtle bg-surface-muted p-2 font-mono text-[11px] text-muted"
            data-testid="error-notice-details"
          >
            {details}
          </pre>
        ) : null}
      </div>
    </Callout>
  );
}
