"use client";

import { useMemo } from "react";
import { CodeBlock } from "@/components/ui/CodeBlock";

type Props = {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  rows?: number;
  readOnly?: boolean;
  testId?: string;
};

/** Shared lightweight Python editor (textarea) — DEV-1/DEV-2/DEV-3. */
export function CodeEditorPanel({
  value,
  onChange,
  label = "Python",
  rows = 16,
  readOnly = false,
  testId = "code-editor",
}: Props) {
  const lineCount = useMemo(() => value.split("\n").length, [value]);

  if (readOnly) {
    return <CodeBlock code={value || "# empty"} language="python" />;
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{label}</span>
        <span>{lineCount} lines</span>
      </div>
      <textarea
        data-testid={testId}
        className="min-h-[12rem] w-full rounded-md border border-border-subtle bg-surface-muted p-3 font-mono text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        spellCheck={false}
      />
    </div>
  );
}
