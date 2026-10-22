"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import {
  bulkErrorGuide,
  sanitizeBulkCopy,
  type BulkErrorContext,
} from "@/lib/bulkSuiteScreen";

type BulkErrorNoticeProps = {
  message: string;
  context: BulkErrorContext;
  className?: string;
  onDismiss?: () => void;
  onRetry?: () => void;
};

/** What happened, why, and the next step. No blame. */
export function BulkErrorNotice({
  message,
  context,
  className,
  onDismiss,
  onRetry,
}: BulkErrorNoticeProps) {
  const guide = bulkErrorGuide(context, message);
  const detail = sanitizeBulkCopy(message.trim());
  return (
    <Callout
      variant="danger"
      title={sanitizeBulkCopy(guide.title)}
      className={className}
      testId="bulk-error-notice"
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
        <p className="text-ink" data-testid="bulk-error-message">
          {detail}
        </p>
      ) : null}
      <p className={detail ? "mt-1" : undefined} data-testid="bulk-error-why">
        {sanitizeBulkCopy(guide.why)}
      </p>
      <p className="mt-1" data-testid="bulk-error-next">
        {sanitizeBulkCopy(guide.next)}
      </p>
    </Callout>
  );
}
