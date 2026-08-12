"use client";

import { useState } from "react";
import { HelpCircle } from "@/components/ui/icons";
import { Tooltip } from "@/components/ui/Tooltip";
import { useShellOptional } from "@/context/ShellContext";
import { api } from "@/lib/api";

type Props = {
  question: string;
  label?: string;
  className?: string;
  model?: string;
  field?: string;
  connectionId?: string;
  draft?: Record<string, unknown>;
};

export function ExplainThisButton({
  question,
  label = "Explain this",
  className,
  model,
  field,
  connectionId,
  draft,
}: Props) {
  const shell = useShellOptional();
  const [busy, setBusy] = useState(false);
  if (!shell) return null;
  const { setUiContext, openExpert } = shell;

  async function handleClick() {
    if (connectionId && model) {
      setBusy(true);
      try {
        const res = await api.expertExplainModel({
          model,
          field,
          draft,
          connection_id: connectionId,
        });
        setUiContext({ model, field, draftSummary: model });
        openExpert({
          question: field ? `Explain ${model}.${field}` : `Explain ${model}`,
          seedQuestion: question,
          seedResponse: res,
          freshThread: true,
        });
        return;
      } catch {
        // fallback
      } finally {
        setBusy(false);
      }
    }
    openExpert({ question, autoSubmit: false });
  }

  return (
    <Tooltip label={label}>
      <button
        type="button"
        className={className ?? "rounded p-1 text-muted hover:bg-surface-muted hover:text-accent"}
        aria-label={label}
        aria-busy={busy}
        data-testid="explain-this"
        disabled={busy}
        onClick={() => void handleClick()}
      >
        <HelpCircle className="h-4 w-4" />
      </button>
    </Tooltip>
  );
}
