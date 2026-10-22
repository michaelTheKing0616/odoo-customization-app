"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import {
  sanitizeSettingsCopy,
  settingsErrorGuide,
  type SettingsErrorContext,
} from "@/lib/settingsScreen";

type SettingsErrorNoticeProps = {
  message: string;
  context: SettingsErrorContext;
  className?: string;
  onDismiss?: () => void;
  onRetry?: () => void;
};

/** What happened, why, and the next step. No blame. */
export function SettingsErrorNotice({
  message,
  context,
  className,
  onDismiss,
  onRetry,
}: SettingsErrorNoticeProps) {
  const guide = settingsErrorGuide(context, message);
  const detail = sanitizeSettingsCopy(message.trim());
  return (
    <Callout
      variant="danger"
      title={sanitizeSettingsCopy(guide.title)}
      className={className}
      testId="settings-error-notice"
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
        <p className="text-ink" data-testid="settings-error-message">
          {detail}
        </p>
      ) : null}
      <p className={detail ? "mt-1" : undefined} data-testid="settings-error-why">
        {sanitizeSettingsCopy(guide.why)}
      </p>
      <p className="mt-1" data-testid="settings-error-next">
        {sanitizeSettingsCopy(guide.next)}
      </p>
    </Callout>
  );
}
