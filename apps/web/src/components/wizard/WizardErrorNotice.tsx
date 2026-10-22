"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import { wizardErrorCopy } from "@/lib/wizard-ui";

type WizardErrorNoticeProps = {
  message: string;
  hasDraft: boolean;
  className?: string;
  onDismiss?: () => void;
};

/** What happened, why (when the message tells us), and the next step. No blame. */
export function WizardErrorNotice({ message, hasDraft, className, onDismiss }: WizardErrorNoticeProps) {
  const copy = wizardErrorCopy({ message, hasDraft });
  return (
    <Callout
      variant="danger"
      title={copy.title}
      className={className}
      testId="error-notice"
      actions={
        <>
          <Button
            variant="ghost"
            size="sm"
            type="button"
            onClick={() => diagnoseWithExpert(copy.message)}
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
      <p className="text-ink" data-testid="error-notice-message">
        {copy.message}
      </p>
      {copy.why ? (
        <p className="mt-1" data-testid="error-notice-why">
          {copy.why}
        </p>
      ) : null}
      <p className="mt-1" data-testid="error-notice-next">
        {copy.next}
      </p>
    </Callout>
  );
}
