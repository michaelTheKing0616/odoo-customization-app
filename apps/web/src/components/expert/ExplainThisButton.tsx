"use client";

import { HelpCircle } from "@/components/ui/icons";
import { Tooltip } from "@/components/ui/Tooltip";
import { useShellOptional } from "@/context/ShellContext";

type Props = {
  question: string;
  label?: string;
  className?: string;
};

export function ExplainThisButton({ question, label = "Explain this", className }: Props) {
  const shell = useShellOptional();
  if (!shell) return null;

  return (
    <Tooltip label={label}>
      <button
        type="button"
        className={className ?? "rounded p-1 text-muted hover:bg-surface-muted hover:text-accent"}
        aria-label={label}
        data-testid="explain-this"
        onClick={() => shell.openExpert({ question })}
      >
        <HelpCircle className="h-4 w-4" />
      </button>
    </Tooltip>
  );
}
