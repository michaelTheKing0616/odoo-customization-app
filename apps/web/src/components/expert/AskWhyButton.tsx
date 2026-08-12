"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useShellOptional } from "@/context/ShellContext";
import { api } from "@/lib/api";

type Props = {
  subject: string;
  context?: string;
  label?: string;
  connectionId?: string;
  draft?: Record<string, unknown>;
  userPrompt?: string;
};

export function AskWhyButton({
  subject,
  context,
  label = "Ask why",
  connectionId,
  draft,
  userPrompt,
}: Props) {
  const shell = useShellOptional();
  const [busy, setBusy] = useState(false);
  if (!shell) return null;
  const { setUiContext, openExpert } = shell;

  async function handleClick() {
    setUiContext({
      model: subject.includes(".") ? subject.split(".")[0] : subject,
      field: subject.includes(".") ? subject.split(".").slice(1).join(".") : undefined,
      draftSummary: context ?? subject,
    });

    if (connectionId && subject && !subject.includes(" ")) {
      setBusy(true);
      try {
        const model = subject.includes(".") ? subject.split(".")[0]! : subject;
        const field = subject.includes(".") ? subject.split(".").slice(1).join(".") : undefined;
        const res = await api.expertExplainModel({
          model,
          field,
          draft,
          user_prompt: userPrompt,
          connection_id: connectionId,
        });
        openExpert({
          question: field
            ? `Explain field ${field} on ${model}`
            : `Explain model ${model}`,
          seedQuestion: field
            ? `Explain field \`${field}\` on \`${model}\``
            : `Explain model \`${model}\``,
          seedResponse: res,
          freshThread: true,
        });
        return;
      } catch {
        // Fall through to generic prefill
      } finally {
        setBusy(false);
      }
    }

    const question = context
      ? `Why did the draft include ${subject}? Context: ${context}`
      : `Why did the draft include ${subject}?`;
    openExpert({ question, autoSubmit: true });
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      loading={busy}
      data-testid="ask-why"
      onClick={() => void handleClick()}
    >
      {label}
    </Button>
  );
}
