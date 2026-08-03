"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";

type ErrorNoticeProps = {
  message: string;
  title?: string;
  className?: string;
  showDiagnose?: boolean;
};

export function ErrorNotice({
  message,
  title = "Request failed",
  className,
  showDiagnose = true,
}: ErrorNoticeProps) {
  return (
    <Callout
      variant="danger"
      title={title}
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
