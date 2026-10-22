"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import {
  sanitizeLiveDemoCopy,
  liveDemoErrorGuide,
  type LiveDemoErrorContext,
} from "@/lib/liveDemoCopilotScreen";

type LiveDemoErrorNoticeProps = {
  message: string;
  context: LiveDemoErrorContext;
  className?: string;
  onDismiss?: () => void;
  onRetry?: () => void;
};

/** What happened, why, and the next step. No blame. */
export function LiveDemoErrorNotice({
  message,
  context,
  className,
  onDismiss,
  onRetry,
}: LiveDemoErrorNoticeProps) {
  const guide = liveDemoErrorGuide(context, message);
  const detail = sanitizeLiveDemoCopy(message.trim());
  return (
    <Callout
      variant="danger"
      title={sanitizeLiveDemoCopy(guide.title)}
      className={className}
      testId="live-demo-error-notice"
      actions={
        <>
          {onRetry ? (
            <Button variant="ghost" size="sm" type="button" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            type="button"
            onClick={() => diagnoseWithExpert(detail || guide.why)}
          >
            Diagnose with Expert
          </Button>
          {onDismiss ? (
            <Button variant="ghost" size="sm" type="button" onClick={onDismiss}>
              Dismiss
            </Button>
          ) : null}
        </>
      }
    >
      {detail ? (
        <p className="text-ink" data-testid="live-demo-error-message">
          {detail}
        </p>
      ) : null}
      <p className={detail ? "mt-1" : undefined} data-testid="live-demo-error-why">
        {sanitizeLiveDemoCopy(guide.why)}
      </p>
      <p className="mt-1" data-testid="live-demo-error-next">
        {sanitizeLiveDemoCopy(guide.next)}
      </p>
    </Callout>
  );
}
