"use client";

import { Button } from "@/components/ui/Button";
import { useShellOptional } from "@/context/ShellContext";

type Props = {
  subject: string;
  context?: string;
  label?: string;
};

export function AskWhyButton({ subject, context, label = "Ask why" }: Props) {
  const shell = useShellOptional();
  if (!shell) return null;
  const question = context
    ? `Why did the draft include ${subject}? Context: ${context}`
    : `Why did the draft include ${subject}?`;
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      data-testid="ask-why"
      onClick={() => {
        shell.setUiContext({ draftSummary: context ?? subject });
        shell.openExpert({ question });
      }}
    >
      {label}
    </Button>
  );
}
