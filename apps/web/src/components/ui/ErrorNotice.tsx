"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";

type ErrorNoticeProps = {
  message: string;
  title?: string;
  className?: string;
  showDiagnose?: boolean;
  onRetry?: () => void;
};

export function ErrorNotice({
  message,
  title = "Request failed",
  className,
  showDiagnose = true,
  onRetry,
}: ErrorNoticeProps) {
  const actions = (
    <>
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
          onClick={() => diagnoseWithExpert(message)}
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
      actions={onRetry || showDiagnose ? actions : undefined}
    >
      {message}
    </Callout>
  );
}
