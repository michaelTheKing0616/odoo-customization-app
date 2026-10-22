"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import {
  powerOpsErrorGuide,
  sanitizePowerOpsCopy,
  type PowerOpsErrorContext,
} from "@/lib/powerOpsScreen";

type PowerOpsErrorNoticeProps = {
  message: string;
  context: PowerOpsErrorContext;
  className?: string;
  onDismiss?: () => void;
  onRetry?: () => void;
};

/** What happened, why, and the next step. No blame. */
export function PowerOpsErrorNotice({
  message,
  context,
  className,
  onDismiss,
  onRetry,
}: PowerOpsErrorNoticeProps) {
  const guide = powerOpsErrorGuide(context, message);
  const detail = sanitizePowerOpsCopy(message.trim());
  return (
    <Callout
      variant="danger"
      title={sanitizePowerOpsCopy(guide.title)}
      className={className}
      testId="power-ops-error-notice"
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
        <p className="text-ink" data-testid="power-ops-error-message">
          {detail}
        </p>
      ) : null}
      <p className={detail ? "mt-1" : undefined} data-testid="power-ops-error-why">
        {sanitizePowerOpsCopy(guide.why)}
      </p>
      <p className="mt-1" data-testid="power-ops-error-next">
        {sanitizePowerOpsCopy(guide.next)}
      </p>
    </Callout>
  );
}
