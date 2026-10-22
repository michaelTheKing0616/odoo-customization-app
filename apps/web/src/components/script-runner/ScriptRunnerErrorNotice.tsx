"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import {
  sanitizeScriptRunnerCopy,
  scriptRunnerErrorGuide,
  type ScriptRunnerErrorContext,
} from "@/lib/scriptRunnerScreen";

type ScriptRunnerErrorNoticeProps = {
  message: string;
  context: ScriptRunnerErrorContext;
  className?: string;
  onDismiss?: () => void;
  onRetry?: () => void;
};

/** What happened, why, and the next step. No blame. */
export function ScriptRunnerErrorNotice({
  message,
  context,
  className,
  onDismiss,
  onRetry,
}: ScriptRunnerErrorNoticeProps) {
  const guide = scriptRunnerErrorGuide(context, message);
  const detail = sanitizeScriptRunnerCopy(message.trim());
  return (
    <Callout
      variant="danger"
      title={sanitizeScriptRunnerCopy(guide.title)}
      className={className}
      testId="script-runner-error-notice"
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
        <p className="text-ink" data-testid="script-runner-error-message">
          {detail}
        </p>
      ) : null}
      <p className={detail ? "mt-1" : undefined} data-testid="script-runner-error-why">
        {sanitizeScriptRunnerCopy(guide.why)}
      </p>
      <p className="mt-1" data-testid="script-runner-error-next">
        {sanitizeScriptRunnerCopy(guide.next)}
      </p>
    </Callout>
  );
}
