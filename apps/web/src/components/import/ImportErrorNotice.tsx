"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import { importErrorGuide, type ImportErrorContext } from "@/lib/importScreen";

type ImportErrorNoticeProps = {
  message: string;
  context: ImportErrorContext;
  className?: string;
  onDismiss?: () => void;
  onRetry?: () => void;
};

/** What happened, why, and the next step. No blame. */
export function ImportErrorNotice({
  message,
  context,
  className,
  onDismiss,
  onRetry,
}: ImportErrorNoticeProps) {
  const guide = importErrorGuide(context, message);
  const detail = message.trim();
  return (
    <Callout
      variant="danger"
      title={guide.title}
      className={className}
      testId="import-error-notice"
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
        <p className="text-ink" data-testid="import-error-message">
          {detail}
        </p>
      ) : null}
      <p className={detail ? "mt-1" : undefined} data-testid="import-error-why">
        {guide.why}
      </p>
      <p className="mt-1" data-testid="import-error-next">
        {guide.next}
      </p>
    </Callout>
  );
}
