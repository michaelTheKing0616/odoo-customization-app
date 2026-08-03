"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";

type ErrorNoticeProps = {
  message: string;
  className?: string;
  showDiagnose?: boolean;
};

export function ErrorNotice({
  message,
  className,
  showDiagnose = true,
}: ErrorNoticeProps) {
  return (
    <Callout
      variant="danger"
      title="Something went wrong"
      className={className}
      testId="error-notice"
      actions={
        showDiagnose ? (
          <Button
            variant="ghost"
            size="sm"
            type="button"
            onClick={() => diagnoseWithExpert(message)}
          >
            Diagnose with Expert
          </Button>
        ) : undefined
      }
    >
      {message}
    </Callout>
  );
}
