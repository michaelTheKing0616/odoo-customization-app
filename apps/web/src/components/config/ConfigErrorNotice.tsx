"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import {
  configErrorGuide,
  sanitizeConfigCopy,
  type ConfigErrorContext,
} from "@/lib/configScreen";

type ConfigErrorNoticeProps = {
  message: string;
  context: ConfigErrorContext;
  className?: string;
  onDismiss?: () => void;
  onRetry?: () => void;
};

/** What happened, why, and the next step. No blame. */
export function ConfigErrorNotice({
  message,
  context,
  className,
  onDismiss,
  onRetry,
}: ConfigErrorNoticeProps) {
  const guide = configErrorGuide(context, message);
  const detail = sanitizeConfigCopy(message.trim());
  return (
    <Callout
      variant="danger"
      title={sanitizeConfigCopy(guide.title)}
      className={className}
      testId="config-error-notice"
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
        <p className="text-ink" data-testid="config-error-message">
          {detail}
        </p>
      ) : null}
      <p className={detail ? "mt-1" : undefined} data-testid="config-error-why">
        {sanitizeConfigCopy(guide.why)}
      </p>
      <p className="mt-1" data-testid="config-error-next">
        {sanitizeConfigCopy(guide.next)}
      </p>
    </Callout>
  );
}
