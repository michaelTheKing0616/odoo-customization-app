"use client";

import { useRef } from "react";
import { highlightCode } from "@/lib/highlight";
import { cn } from "@/lib/cn";

export type LineDiagnostic = {
  line: number;
  message: string;
};

type Props = {
  value: string;
  onChange: (value: string) => void;
  label: string;
  diagnostics?: LineDiagnostic[];
  testId?: string;
  /** Called on Cmd+Enter / Ctrl+Enter from any line. */
  onSubmit?: () => void;
  /** Hide the built-in label row when the caller draws its own editor chrome. */
  showHeader?: boolean;
  className?: string;
};

export function PythonLineEditor({
  value,
  onChange,
  label,
  diagnostics = [],
  testId = "python-line-editor",
  onSubmit,
  showHeader = true,
  className,
}: Props) {
  const lines = value.length > 0 ? value.split("\n") : [""];
  const inputs = useRef<Array<HTMLInputElement | null>>([]);
  const labelId = `${testId}-label`;

  function commit(next: string[]) {
    onChange(next.join("\n"));
  }

  function focusLine(index: number, column: number) {
    const el = inputs.current[index];
    if (!el) return;
    el.focus();
    const pos = Math.max(0, Math.min(column, el.value.length));
    requestAnimationFrame(() => el.setSelectionRange(pos, pos));
  }

  return (
    <div className={cn("space-y-1", className)}>
      {showHeader ? (
        <div className="flex items-center justify-between text-xs text-muted">
          <span id={labelId}>{label}</span>
          <span className="tabular-nums">
            {lines.length} {lines.length === 1 ? "line" : "lines"}
          </span>
        </div>
      ) : null}
      <div
        role="group"
        aria-labelledby={showHeader ? labelId : undefined}
        aria-label={showHeader ? undefined : label}
        data-testid={testId}
        className="python-line-editor code-block-highlight max-h-[28rem] overflow-auto overscroll-contain rounded-md border border-border-subtle bg-surface-muted py-1"
      >
        {lines.map((line, index) => {
          const lineNo = index + 1;
          const diag = diagnostics.filter((item) => item.line === lineNo);
          const diagId = diag.length > 0 ? `${testId}-diag-${lineNo}` : undefined;
          return (
            <div
              key={index}
              data-invalid={diag.length > 0 ? "true" : undefined}
              className={cn(
                "grid w-max min-w-full grid-cols-[2.75rem_minmax(0,1fr)] items-start",
                diag.length > 0 && "bg-danger-subtle",
              )}
            >
              <span
                className={cn(
                  "sticky left-0 select-none bg-surface-muted py-0.5 pr-2 text-right font-mono text-xs leading-6 tabular-nums text-subtle",
                  diag.length > 0 && "bg-danger-subtle text-danger",
                )}
                aria-hidden="true"
              >
                {lineNo}
              </span>
              <div className="relative min-w-0 font-mono text-sm leading-6">
                <pre
                  aria-hidden="true"
                  className="pointer-events-none whitespace-pre py-0.5 pl-2 pr-6 text-ink"
                >
                  <code
                    dangerouslySetInnerHTML={{
                      __html: highlightCode(line.length > 0 ? line : " ", "python"),
                    }}
                  />
                </pre>
                <input
                  ref={(node) => {
                    inputs.current[index] = node;
                  }}
                  value={line}
                  aria-label={`Line ${lineNo}`}
                  aria-invalid={diag.length > 0 ? true : undefined}
                  aria-describedby={diagId}
                  spellCheck={false}
                  autoCapitalize="off"
                  autoCorrect="off"
                  className="absolute inset-0 w-full border-0 bg-transparent py-0.5 pl-2 pr-6 font-mono text-sm leading-6 text-transparent caret-ink outline-none focus-visible:bg-accent/5 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent"
                  onChange={(event) => {
                    const next = lines.slice();
                    next[index] = event.target.value.replace(/[\r\n]/g, "");
                    commit(next);
                  }}
                  onPaste={(event) => {
                    const text = event.clipboardData.getData("text");
                    if (!text.includes("\n") && !text.includes("\r")) return;
                    event.preventDefault();
                    const pasted = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
                    const el = event.currentTarget;
                    const start = el.selectionStart ?? line.length;
                    const end = el.selectionEnd ?? start;
                    const head = line.slice(0, start) + pasted[0];
                    const tail = pasted[pasted.length - 1] + line.slice(end);
                    const middle = pasted.slice(1, -1);
                    commit([
                      ...lines.slice(0, index),
                      head,
                      ...middle,
                      tail,
                      ...lines.slice(index + 1),
                    ]);
                  }}
                  onKeyDown={(event) => {
                    const el = event.currentTarget;
                    const start = el.selectionStart ?? 0;
                    const end = el.selectionEnd ?? start;
                    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                      if (onSubmit) {
                        event.preventDefault();
                        onSubmit();
                      }
                      return;
                    }
                    if (event.key === "Enter") {
                      event.preventDefault();
                      commit([
                        ...lines.slice(0, index),
                        line.slice(0, start),
                        line.slice(start),
                        ...lines.slice(index + 1),
                      ]);
                      requestAnimationFrame(() => focusLine(index + 1, 0));
                      return;
                    }
                    if (event.key === "Backspace" && start === 0 && end === 0 && index > 0) {
                      event.preventDefault();
                      const prev = lines[index - 1] ?? "";
                      commit([
                        ...lines.slice(0, index - 1),
                        prev + line,
                        ...lines.slice(index + 1),
                      ]);
                      requestAnimationFrame(() => focusLine(index - 1, prev.length));
                      return;
                    }
                    if (event.key === "ArrowUp" && index > 0) {
                      event.preventDefault();
                      focusLine(index - 1, start);
                      return;
                    }
                    if (event.key === "ArrowDown" && index < lines.length - 1) {
                      event.preventDefault();
                      focusLine(index + 1, start);
                    }
                  }}
                />
              </div>
              {diag.length > 0 ? (
                <p
                  id={diagId}
                  role="alert"
                  className="sticky left-11 col-start-2 max-w-[34ch] whitespace-normal pb-1.5 pl-2 pr-3 text-xs leading-5 text-danger sm:max-w-[60ch]"
                >
                  {diag.map((item) => item.message).join(" ")}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
      {value.trim() === "" ? (
        <p className="text-xs text-muted">No code yet. Write a server-action body, or insert a snippet.</p>
      ) : null}
    </div>
  );
}
