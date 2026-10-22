"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import {
  journalErrorGuide,
  sanitizeJournalCopy,
  type JournalErrorContext,
} from "@/lib/journalScreen";

type JournalErrorNoticeProps = {
  message: string;
  context: JournalErrorContext;
  className?: string;
  onDismiss?: () => void;
  onRetry?: () => void;
};

/** What happened, why, and the next step. No blame. */
export function JournalErrorNotice({
  message,
  context,
  className,
  onDismiss,
  onRetry,
}: JournalErrorNoticeProps) {
  const guide = journalErrorGuide(context, message);
  const detail = sanitizeJournalCopy(message.trim());
  return (
    <Callout
      variant="danger"
      title={sanitizeJournalCopy(guide.title)}
      className={className}
      testId="journal-error-notice"
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
        <p className="text-ink" data-testid="journal-error-message">
          {detail}
        </p>
      ) : null}
      <p className={detail ? "mt-1" : undefined} data-testid="journal-error-why">
        {sanitizeJournalCopy(guide.why)}
      </p>
      <p className="mt-1" data-testid="journal-error-next">
        {sanitizeJournalCopy(guide.next)}
      </p>
    </Callout>
  );
}
